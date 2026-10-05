# header for Keysight/Agilent InfiniiVision DSOX1204G oscilloscope

import time
import numpy as np
import pyvisa


class DSOX1204G:
    """Driver for a Keysight/Agilent DSOX1204G (or similar InfiniiVision
    series) oscilloscope, talking SCPI over USBTMC or LAN via PyVISA."""

    def __init__(self, resource=None, backend="@py", timeout_ms=15000):
        self.rm = pyvisa.ResourceManager(backend)

        if resource is None:
            resource = self._autodetect(self.rm)

        self.inst = self.rm.open_resource(resource)
        self.inst.timeout = timeout_ms
        self.inst.read_termination = "\n"
        self.inst.write_termination = "\n"

        self.name = self.inst.query("*IDN?").strip()
        print(f"Connected to: {self.name}")

    @staticmethod
    def _autodetect(rm):
        """Pick the first USB VISA resource that looks like an instrument."""
        resources = rm.list_resources()
        print(resources)
        usb_matches = [r for r in resources if r.startswith("USB")]
        if not usb_matches:
            raise RuntimeError(
                f"No USB VISA resource found. Available resources: {resources}. "
                "If connecting over LAN instead, pass resource="
                "'TCPIP0::<scope ip>::inst0::INSTR' explicitly."
            )
        return usb_matches[0]

    # ---- low level helpers -------------------------------------------------

    def write(self, command):
        self.inst.write(command)

    def query(self, command):
        return self.inst.query(command).strip()

    def close(self):
        self.inst.close()

    # ---- waveform capture ---------------------------------------------------

    def _channel_is_on(self, channel):
        return self.query(f":CHANnel{channel}:DISPlay?") == "1"

    def get_channel_waveform(self, channel=1, points_mode="RAW", max_points=None):
        """
        Pull the currently-displayed waveform record for one channel and
        return (t, v) as numpy arrays in seconds / volts.

        The scope should already be stopped (see get_all_channels) so that
        RAW mode returns the full acquisition memory rather than just the
        on-screen decimated trace.
        """
        if not self._channel_is_on(channel):
            return None, None

        self.write(f":WAVeform:SOURce CHANnel{channel}")
        self.write(":WAVeform:FORMat BYTE")
        self.write(f":WAVeform:POINts:MODE {points_mode}")
        if max_points is not None:
            self.write(f":WAVeform:POINts {int(max_points)}")

        preamble = self.query(":WAVeform:PREamble?").split(",")
        # format, type, points, count, xincrement, xorigin, xreference,
        # yincrement, yorigin, yreference
        x_increment = float(preamble[4])
        x_origin = float(preamble[5])
        x_reference = float(preamble[6])
        y_increment = float(preamble[7])
        y_origin = float(preamble[8])
        y_reference = float(preamble[9])

        raw = self.inst.query_binary_values(
            ":WAVeform:DATA?", datatype="B", container=np.array
        )

        v = (raw.astype(np.float64) - y_reference) * y_increment + y_origin
        t = (np.arange(len(raw), dtype=np.float64) - x_reference) * x_increment + x_origin

        return t, v

    def get_all_channels(self, channels=(1, 2, 3, 4), points_mode="RAW",
                          max_points=None, resume_run=True):
        """
        Primary function: stop acquisition, grab every currently-enabled
        channel's full waveform record, then (optionally) resume running.

        Returns a dict: {channel_number: (t, v)} for each channel that is
        turned on. Channels that are off are skipped.
        """
        was_running = self.query(":OPERegister:CONDition?") if False else None
        self.write(":STOP")
        time.sleep(0.1)  # let the scope settle after stopping

        data = {}
        for ch in channels:
            t, v = self.get_channel_waveform(
                channel=ch, points_mode=points_mode, max_points=max_points
            )
            if t is not None:
                data[ch] = (t, v)
            else:
                # print(f"Channel {ch}: off, skipped")
                pass

        if resume_run:
            self.write(":RUN")

        return data

    def save_waveforms(self, filepath, downsampling = 1):
        """
        Save a {channel: (t, v)} dict (as returned by get_all_channels)
        to a single .npz file at filepath, e.g. 'C:/data/run1.npz'.
        """
        data = self.get_all_channels()

        try:
            data_number_file = "code/data/data_number.txt"
            with open(data_number_file, "r") as f:
                data_number = int(f.read())
            with open(data_number_file, "w") as f:
                f.write(str(data_number + 1))

        except FileNotFoundError:
            data_number_file = "data/data_number.txt"
            with open(data_number_file, "r") as f:
                data_number = int(f.read())
            with open(data_number_file, "w") as f:
                f.write(str(data_number + 1))
        save_dict = {}
        for ch, (t, v) in data.items():
            save_dict[f"t{ch}"] = t[::downsampling]
            save_dict[f"v{ch}"] = v[::downsampling]
        np.savez(f"{filepath}_{data_number}.npz", **save_dict)
        return f"{filepath}_{data_number}.npz"

    def capture_on_trigger(self, filepath, num_captures, channels=(1, 2, 3, 4), timeout_s=20, downsampling=1):
        """
        For scopes that trigger periodically (e.g. every ~10s): captures
        the FULL record for each trigger the scope actually completes,
        skipping cycles where no trigger arrives in time. Fixes the
        'stopped mid-trace' issue you get from a fixed-time RUN/sleep/STOP
        loop -- that approach stops the scope by the clock, not by whether
        the acquisition (post-trigger record fill) has actually finished.

        Uses :DIGitize, which arms, blocks until a trigger occurs AND the
        full record is acquired, then auto-stops the scope -- so the
        waveform is always complete when we read it. *OPC? is used to
        wait for that to finish; if no trigger shows up within timeout_s,
        that cycle is skipped and the next one begins.
        """
        old_timeout = self.inst.timeout
        self.inst.timeout = int(timeout_s * 1000)

        chan_list = ",".join(f"CHANnel{c}" for c in channels)
        n_saved = 0
        try:
            for i in range(num_captures):
                self.write(f":DIGitize {chan_list}")
                try:
                    self.query("*OPC?")  # blocks until acquisition is truly done
                except pyvisa.errors.VisaIOError:
                    print(f"Cycle {i}: no trigger within {timeout_s}s, skipping")
                    continue

                fp = self.save_waveforms(filepath, downsampling)
                n_saved += 1
                print(f"Saved capture {n_saved} -> {fp}")
        finally:
            self.inst.timeout = old_timeout

        print(f"Done: {n_saved}/{num_captures} triggers captured")

def load_waveforms(filepath):
    """
    Load a .npz file saved by save_waveforms back into a
    {channel: (t, v)} dict.
    """
    npz = np.load(filepath)
    data = {}
    for key in npz.files:
        if key.startswith("t"):
            ch = int(key[1:])
            data[ch] = (npz[f"t{ch}"], npz[f"v{ch}"])
    return data


def self_test():
    # USB example:
    scope = DSOX1204G()
    # LAN example instead:
    # scope = DSOX1204G(resource="TCPIP0::192.168.1.50::inst0::INSTR")

    data = scope.get_all_channels()
    for ch, (t, v) in data.items():
        print(f"CH{ch}: {len(v)} points, span = {t[-1]-t[0]:.6g} s")

    scope.close()
    return data


if __name__ == "__main__":
    scope = DSOX1204G()
    data = scope.get_all_channels()
    scope.save_waveforms(data, "code/data/22/test")