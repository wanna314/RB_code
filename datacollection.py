from scope_header import DSOX1204G, self_test, load_waveforms
import time

scope = DSOX1204G()


# capturing multiple triggers
start = time.time()
scope.capture_on_trigger(filepath="code/data/32/splittings/2Vpp", num_captures=25, channels=(1, 2), timeout_s=10, downsampling=10)
end = time.time()
print(f"Time taken: {end - start:.2f} seconds")

# capture what is on the scope
# scope.save_waveforms("code/data/32/0.1ms_pulse", downsampling=10)