import numpy as np

def ammeter(V, fullrange = 1e-9): # V in mV
    return fullrange / 1e-9 * 0.01e-9 * V # in A

def ammeter_uncertainty(V, sigma_V = 0, fullrange = 1e-9): # V in mV
    m = fullrange / 1e-9 * 0.01e-9
    return np.sqrt(m**2 * sigma_V**2  + V**2 * (0.00002e-9)**2 ) # in A


def gaussmeter(V): # in V
    return 0.002007 * V + 0.01 # in G

def gaussmeter_uncertainty(V, sigma_V = 0): # in V
    m = 0.002007
    return np.sqrt(m**2 * sigma_V**2  + V**2 * (0.0000001)**2) # in G # + (0.002)**2



def vertical_coils(current): # in A
    return 3.23 * current - 0.48 # in G

def vertical_coils_uncertainty(current, sigma_current = 0, relative = False): # in A
    m = 3.23
    sigma_m = 0.02
    sigma_b = 0.02
    if relative:
        sigma_b = 0 
    return np.sqrt(m**2 * sigma_current**2 + sigma_b**2 + current**2 * sigma_m**2)  

def horizontal_coils(current): # in A
    return 3.28 * current + 0.04 # in G

def horizontal_coils_uncertainty(current, sigma_current = 0, relative = False): # in A
    m = 3.28
    sigma_m = 0.02
    sigma_b =  0.02
    if relative:
        sigma_b = 0
    return np.sqrt(m**2 * sigma_current**2 + sigma_b**2 + current**2 * sigma_m**2)

def modulation_coils(current): # in A
    return 1.69 * current + 0.02 # in G

def modulation_coils_uncertainty(current, sigma_current = 0, relative = False): # in A
    m = 1.69
    sigma_m = 0.07
    sigma_b =  0.02
    if relative:
        sigma_b = 0
    return np.sqrt(m**2 * sigma_current**2 + sigma_b**2 + current**2 * sigma_m**2)

def corrected_field(field):
    return 0.9919 * field

def corrected_field_error(field):
    return 0.0005 / 0.9919 * field