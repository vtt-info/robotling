# Blue HexBug
from micropython import const
from robotling_board import *

# Tilt-sensing
PIRO_MAX_ANGLE   = const(25)   # Maximal tilt (i.e. pitch/roll) allowed
                               # .. before robot responds
# Obstacle/cliff detection
AI_CH_IR_RANGING = const(0)    # Analog-In channel for IR distance sensor
MAX_IR_SCAN_POS  = const(3)    # Scan positions to check for obstacles/cliffs
DIST_OBST_CM     = const(7)    # Lower distances are considered obstacles
DIST_CLIFF_CM    = const(20)   # Farer distances are considered cliffs

# Servo settings
DO_CH_DIST_SERVO = DIO0        # Digital-Out channel for distance sensor servo
MIN_DIST_SERVO   = const(45)   # Limits of servo that holds the arm with the
MAX_DIST_SERVO   = const(-45)  # .. IR distance sensor in [°]
MIN_US_SERVO     = const(1322) # Minimum timing of servo in [us]
MAX_US_SERVO     = const(2350) # Maximum timing of servo in [us]
SCAN_DIST_SERVO  = const(-25)  # Angle of IR distance sensor arm

# Period of timer that keeps sensor values updated, the NeoPixel pulsing,
# and checks for tilt (in [ms])
TM_PERIOD        = const(50)

# Default motor speeds ..
SPEED_WALK       = const(-75)  # -55,-70 .. for walking forwards
SPEED_TURN       = const(35)   # +25,+30 .. for turning head when changing direction
SPEED_TURN_DELAY = const(900)  #
SPEED_BACK_DELAY = const(500)  #
SPEED_SCAN       = const(40)   # .. for turning head when scanning

# Options, depending on sensor complement
USE_COMPASS      = const(0)    #
HEAD_ADJUST_FACT = const(-1)   #
HEAD_ADJUST_THR  = const(5)    # [°]

USE_LOAD_SENSING = const(0)    # AI channels #6,7 for load-sensing

# Additional devices plugged into the robotling board
MORE_DEVICES     = ["compass_cmps12"]
#MORE_DEVICES    = ["compass_cmps12", "vl6180x"]
#MORE_DEVICES    = ["lsm303"]
#MORE_DEVICES    = ["lsm303", "dotstar_feather"]
