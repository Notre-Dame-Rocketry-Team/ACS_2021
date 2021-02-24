"""
This file contains code relating to
controlling the servo, mostly PID
or some subset of it, with gain 
scheduling or whatever fancy stuff
you guys do
"""

# Import modules
import numpy as np
import matplotlib.pyplot as plt
import data_manager
from data_manager import Data_Manager
# import openpyxl

# Global Variables
angle = 0
angle_min = 0
angle_max = 70 # degrees. Mechanism is changing so don't actually know if this is right
extension = 0  # 0 no extension, 1 full extension
flightAltitude = []
flightVelocity = []
flightAccel = []
# Function definitions
def initialize(manager: Data_Manager):
    manager.add_data(data_manager.Scalar_Data('control_extension'))
    manager.add_data(data_manager.Scalar_Data('control_angle'))

def step(manager: Data_Manager):
    """
    Author: Nick Crnkovich
    This function should perform a computation
    step which takes in sensor data and updates
    the current recommended angle
    Input: data - output from filter, will
    be an ordered pair of data
    Output: None
    """
    
    # Read data
    state = manager.read_field('state').get_value()
    height = manager.read_field('kalman_height').get_value()
    velocity = manager.read_field('kalman_velocity').get_value()
    acceleration = manager.read_field('kalman_acceleration').get_value()
    extension = manager.read_field('control_extension').get_value()

    if state == 'Burnout':
        # Set parameters
        # c = 1125.3  # [fps] speed of sound
        c = 343  #[m/s] speed of sound
        w_tabs = 1.71*0.0254  # [in to m] tab width
        L_max_tabs = 1.4*0.0254  # [in to m] max tab length/extension
        rho = 1.225  #[kg/m**3] density of air
        M_e = 303/35.274  # [oz to kg] EMPTY mass of rocket
        g = 9.81  # [m/s**2] gravity
        theta = 0*np.pi/180  # [degrees to radians] launch angle
        dt = 0.1  # [s] time step size
        targetApogee = 1615.44  # [m]

        # Initial conditions for simulation at BURNOUT, initalize variables for in flight
        ax_R = 0  # [m/s**2] rocket acceleration
        ay_R = acceleration 
        Vx_R = 0 
        Vy_R = velocity  # [m/s] rocket vertical velocity 
        x_R = 0  # [m] rocket x position
        alt_R = height # [m] rocket altitude

        ## Run Runge Kutta to predict apogee

        # calculations
        Vmag_R = np.sqrt(Vx_R**2 + Vy_R**2) 
        Mach = Vmag_R/c  # Mach number

        if Mach >= 1:
            Mach = 0.99

        # Tab drag
        # Empirical fit for incompressible coefficient of drag tabs
        Cd_o_tabs = 10**(0.44*extension - 0.7) 
        # adjusted for compressibility
        Cd_tabs = 1/np.sqrt(1-Mach**2)*Cd_o_tabs 

        # area of tabs as function of extension
        A_tabs = 4*w_tabs*(extension*L_max_tabs)  

        # rocket drag
        Cd_rocket = 0.145
        A_rocket = (6.17*0.0254/2)**2*np.pi  # [diamter in to m] [m**2]


        # Runge Kutta
        # update with new sensor data
        VySim = Vy_R 
        VxSim = Vx_R 
        VmagSim = np.sqrt(VySim**2 + VxSim**2)  # magnitude of velocity vector from data
        axSim = ax_R 
        aySim = ay_R 
        altSim = alt_R 
        xSim = x_R 

        while VySim > 0:  
            # k1vx = fx(VmagSim, Cd_rocket, Cd_tabs, A_tabs, theta, M_e) 
            k1vy = dt*fy(VmagSim, Cd_rocket, Cd_tabs, A_tabs, theta, M_e) 
            # k1rx = VxSim 
            k1ry = dt*VySim 
            
            # k2vx = fx(VmagSim + 0.5*dt*k1rx, Cd_rocket, Cd_tabs, A_tabs, theta, M_e) 
            k2vy = dt*fy(VmagSim + 0.5*k1vy, Cd_rocket, Cd_tabs, A_tabs, theta, M_e) 
            # k2rx = VxSim*k1vx*dt/2 
            k2ry = dt*(VySim + k1vy/2)
            
            # k3vx = fx(VmagSim + 0.5*dt*k2rx, Cd_rocket, Cd_tabs, A_tabs, theta, M_e) 
            k3vy = dt*fy(VmagSim + 0.5*k2vy, Cd_rocket, Cd_tabs, A_tabs, theta, M_e) 
            # k3rx = VxSim*k2vx*dt/2 
            k3ry = dt*(VySim + k2vy/2)
            
            # k4vx = fx(VmagSim + dt*k3rx, Cd_rocket, Cd_tabs, A_tabs, theta, M_e) 
            k4vy = dt*fy(VmagSim + k3vy, Cd_rocket, Cd_tabs, A_tabs, theta, M_e) 
            # k4rx = VxSim*k3vx*dt 
            k4ry = dt*(VySim + k3vy)
            
            # Find values at next timeStep
            # VxSim = VxSim + dt/6.0*(k1vx + 2.0*k2vx + 2.0*k3vx + k4vx) 
            VySim = VySim + 1.0/6.0*(k1vy + 2.0*k2vy + 2.0*k3vy + k4vy) 
            VmagSim = np.sqrt(VxSim**2 + VySim**2) 
            
            # xSim = xSim + dt/6.0*(k1rx + 2*k2rx + 2*k3rx + k4rx) 
            altSim = altSim + 1.0/6.0*(k1ry + 2*k2ry + 2*k3ry + k4ry) 
            
            # Calculate new drag coefficient for tabs/(rocket?)
            Mach = VmagSim/c
            Cd_tabs = 1/np.sqrt(1-Mach**2)*Cd_o_tabs 

        SimApogee = altSim 
        error = SimApogee - targetApogee 

        
     ## PID/angle selection
    # if error < 0:
    #     extension = 0  # if simulated apogee is below target, stop
    # elif error > 100: 
    #     extension = 1  # if simulated apogee is > 100 m above target, full extension
    # else:

        dExt = 0.0007*error
        extension = extension + dExt
    
        if extension > 1:
            extension = 1 
        elif extension < 0:
            extension = 0 

    elif state == 'Overshoot':
        extension = 1
        
    else:
        extension = 0

    manager.update_field('control_extension', extension)

    return extension


def get_angle(manager: Data_Manager):
    """
    Author: Nick Crnkovich
    This function should output the current
    angle the servo should be extended to
    Input: None
    Output: current angle
    """
    extension = manager.read_field('control_extension').get_value()
    servo_angle = extension*angle_max
    manager.update_field('control_angle', servo_angle)

    return servo_angle

def get_min():
    """
    Author:
    This function should output the minimum
    angle the servo can be rotated to
    Input: None
    Output: minimum angle
    """
    angle_min = 0
    return angle_min

def get_max():
    """
    Author:
    This function should output the maximum
    angle the servo can be rotated to
    Input: None
    Output: maximum angle
    """
    angle_max = 70

    return angle_max

# functions to be used for RK

def fy(V, Cd_rocket, Cd_tabs, A_tabs, theta, M_e):
    rho = 1.225 #[kg/m **3] density of air
    g = 9.81 # [m/s **2] gravity
    A_rocket = (6.17*0.0254/2)**2*np.pi # [diamter in to m] [m**2]

    Ky = (-0.5*rho*Cd_rocket*V**2*A_rocket*np.sin(theta) - 0.5*rho*Cd_tabs*V**2*A_tabs*np.sin(theta) - M_e*g)/M_e

    return Ky
 
def fx(V, Cd_rocket, Cd_tabs, A_tabs, theta, M_e):
    rho = 1.225 #[kg/m**3] density of air
    g = 9.81 #[m/s**2] gravity
    A_rocket = (6.17*0.0254/2)**2*np.pi # [diamter in to m] [m**2]

    Kx = (-0.5*rho*Cd_rocket*V**2*A_rocket*np.cos(theta) - 0.5*rho*Cd_tabs*V**2*A_tabs*np.cos(theta))/M_e
    return Kx
