import scipy.integrate
import numpy as np

import simtk.unit as u

import permeability_functions.misc as misc

# 1) Compute means and force autocorrelations
# 2) Integrate force correlations over time and get diffusion
# 3) Integrate mean forces over distance and get free energy
# 4) Use inhomogeneous-diffusion solubility model to get resistance over distance
# 5) Invert resistance to get permeability

def permeability_routine(reaction_coordinates, mean_forces, facf_integrals):
    """ Umbrella function that calls functions to look at free energy,
    diffusion, resistance, and permeability """
    reaction_coordinates = misc.validate_quantity_type(reaction_coordinates, 
                                                        u.nanometer)
    mean_forces = misc.validate_quantity_type(mean_forces, 
                                            u.kilocalorie/(u.mole*u.angstrom))

    facf_integrals = misc.validate_quantity_type(facf_integrals, 
                                (u.kilocalorie/(u.mole*u.angstrom))**2*u.picosecond)

    fe_profile = compute_free_energy_profile(mean_forces,
                                                            reaction_coordinates)

    diffusion_profile = compute_diffusion_coefficient(
                                                            facf_integrals)

    resistance_profile, resistance_integral = compute_resistance_profile(
                                                    fe_profile, 
                                                    diffusion_profile, 
                                                    reaction_coordinates)
    permeability_profile = compute_permeability(resistance_profile)
    permeability_profile = permeability_profile.in_units_of(u.centimeter**2/u.second)

    permeability_integral = compute_permeability(resistance_integral)
    permeability_integral = permeability_integral.in_units_of(u.centimeter/u.second)

    return (reaction_coordinates, mean_forces, facf_integrals, fe_profile, diffusion_profile, resistance_profile, resistance_integral, permeability_profile, permeability_integral)

def analyze_force_timeseries(times, forces, meanf_name=None, fcorr_name=None,
                            correlation_length=300*u.picosecond):
    """ Given a timeseries of forces, compute force autocorrealtions and means"""
    mean_force = np.mean(forces)
    times = misc.validate_quantity_type(times, u.picosecond)
    dstep = times[1] - times[0]
    funlen = int(correlation_length/dstep)
    FACF = acf(forces, funlen, dstart=10)
    time_intervals = np.arange(0, funlen*dstep._value, dstep._value )*dstep.unit
    time_intevals = misc.validate_quantity_type(time_intervals, dstep.unit)
    times_facf = np.column_stack((time_intervals, FACF))
    if fcorr_name:
        np.savetxt(fcorr_name, times_facf)
    if meanf_name:
        np.savetxt(meanf_name, [mean_force._value])

    return mean_force, time_intervals, FACF

def acf(forces, funlen, dstart=10):
    """Calculate the autocorrelation of a function

    Params
    ------
    forces : np.ndarray, shape=(n,)
        The force timeseries acting on a molecules
    timestep : float
        Simulation timestep in fs
    funlen : int
        The desired length of the correlation function

    Returns
    -------
    corr : np.array, shape=(funlen,)
        The autocorrelation of the forces
    """    
    if funlen > forces.shape[0]:
       raise Exception("Not enough data")
    # number of time origins
    ntraj = int(np.floor((forces.shape[0]-funlen)/dstart))
    meanfz = np.mean(forces)
    f1 = np.zeros((funlen)) * meanfz.unit**2
    origin = 0 
    for i in range(ntraj):
        dfzt = (forces[origin:origin+funlen] - meanfz)
        dfz0 = (forces[origin] - meanfz)
        f1 += dfzt*dfz0
        origin += dstart
    return f1/ntraj


def integrate_facf_over_time(times, facf, average_fraction=0.1):
    """ Integrate force autocorelations

    Notes
    -----
    We're doing a cumulative sum, but average the 'last bit' in order 
    to average out the noise
    """
    intF = np.cumsum(facf)*facf.unit * (times[1]-times[0])
    lastbit = int((1.0-average_fraction)*intF.shape[0])
    intFval = np.mean(intF[-lastbit:])

    return intF, intFval

def compute_free_energy_profile(forces, reaction_coordinates):
    """
    forces : array of floats, u.Quantity
    reaction_coordinates: array of floats, u.Quantity

    Notes
    -----
    Forces and reaction_coordinates are u.Quantity, but the elements should just be floats
    """
    forces = misc.validate_quantity_type(forces, (u.kilocalorie / (u.mole * u.angstrom)))
    reaction_coordinates = misc.validate_quantity_type(reaction_coordinates, u.angstrom)

    return -scipy.integrate.cumtrapz(forces._value, x=reaction_coordinates._value, initial=0)*forces.unit*reaction_coordinates.unit

def compute_diffusion_coefficient(intfacf, 
                                kb=1.987e-3 * u.kilocalorie / (u.mole * u.kelvin),
                                temp=305*u.kelvin):
    intfacf = misc.validate_quantity_type(intfacf, (u.kilocalorie / (u.mole * u.angstrom))**2 * u.picosecond)
    

    RT2 = (kb*temp)**2
    diffusion_coefficient = (RT2/intfacf).in_units_of(u.centimeter**2/u.second)

    return diffusion_coefficient

def compute_resistance_profile(fe_profile, diff_profile, reaction_coordinates,
                                kb=1.987e-3 * u.kilocalorie / (u.mole * u.kelvin),
                                temp=305*u.kelvin):
    fe_profile = misc.validate_quantity_type(fe_profile, u.kilocalorie/u.mole)
    
    diff_profile = misc.validate_quantity_type(diff_profile, u.centimeter**2/u.second)
    
    numerator = np.exp(fe_profile/(kb*temp))
    integrand = numerator/diff_profile
    return integrand, scipy.integrate.trapz(integrand, x=reaction_coordinates) * reaction_coordinates.unit/diff_profile.unit

def compute_permeability(resistance):
    return 1/resistance


