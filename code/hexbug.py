# ----------------------------------------------------------------------------
# hexbug.py
# Definition of the class `Hexbug`, derived from `Robotling`
#
# Example code for a "hijacked" HexBug. Uses the IR distance sensor to
# avoid obstacles and cliffs simply by checking if the distance measured is
# within the range expected for the surface in front of the robot (~ 6 cms).
# If a shorter or farer distance is measured, the robot turns in a random
# direction until it detects the ground again. To cover the ground in front
# of the robot, the IR sensor is moved back and forth sideways and the
# average of the measured distances is used for making the obstacle/ground/
# cliff decision.
# In parallel, all motors are stopped and the NeoPixel turns from green to
# violet dif robot is tilted (e.g. falls on the side); for this, pitch/roll
# provided by the compass (time-filtered) are checked.
#
# The MIT License (MIT)
# Copyright (c) 2018 Thomas Euler
# 2018-09-13, first release.
# 2018-10-29, use pitch/roll to check if robot is tilted.
# 2018-11-03, some cleaning up and commenting of the code
# 2018-11-28, re-organised directory structure, collecting all access to
#             hardware specifics to a set of "adapter classes" in `platform`,
# 2018-12-22, reorganised into a module with the class `Hexbug` and a simpler
#             main program file (`main.py`). All hardware-related settings
#             moved to separate file (`hexbug_config-py`)
# 2019-01-01, vl6180x time-of-flight distance sensor support added
# ----------------------------------------------------------------------------
import array
import random
from micropython import const
import robotling_board as rb
import driver.drv8835 as drv8835
from robotling import Robotling
from robotling_board_version import BOARD_VER
from motors.dc_motor import DCMotor
from motors.servo import Servo
from misc.helpers import TemporalFilter
from hexbug_config import *

from platform.platform import platform
if platform.ID == platform.ENV_ESP32_UPY:
  import time
else:
  import platform.m4ex.time as time

# ----------------------------------------------------------------------------
# Robot states
STATE_IDLE       = const(0)
STATE_WALKING    = const(1)
STATE_LOOKING    = const(2)
STATE_ON_HOLD    = const(3)
STATE_OBSTACLE   = const(4)
STATE_CLIFF      = const(5)

# NeoPixel colors (r,g,b) for the different states
STATE_COLORS     = bytearray((
                   10,10,10,   # STATE_IDLE
                   20,70,0,    # STATE_WALKING
                   40,30,0,    # STATE_LOOKING
                   20,00,50,   # STATE_ON_HOLD
                   90,30,0,    # STATE_OBSTACLE
                   90,0,30))   # STATE_CLIFF

# ----------------------------------------------------------------------------
class HexBug(Robotling):
  """Hijacked-HexBug class"""

  def __init__(self, devices):
    super().__init__(devices)

    # Check if VL6180X time-of-flight ranging sensor is present, if not, add
    # analog IR ranging sensor (expected to be connected to A/D channel #0)
    try:
      self.RangingSensor = self._VL6180X
      if not self.RangingSensor.isReady:
        raise AttributeError
    except:
      from sensors.sharp_ir_ranging import SharpIRRangingSensor_GP2Y0A41SK0F
      self.RangingSensor = SharpIRRangingSensor_GP2Y0A41SK0F(self._MCP3208,
                                                             AI_CH_IR_RANGING)
      self._MCP3208.channelMask |= 0x01 << AI_CH_IR_RANGING
    print("Using {0} as ranging sensor".format(self.RangingSensor.name))

    # Define scan positions to cover the ground before the robot. Currently,
    # the time the motor is running (in [s]) is used to define angular
    # position
    self._distData = array.array("f", [0] *MAX_IR_SCAN_POS)
    self._scanPos  = [-450, 500, -250]
    self.onTrouble = False

    # Add the servo that moves the ranging sensor up and down
    self.ServoRangingSensor = Servo(DO_CH_DIST_SERVO,
                                    us_range=[MIN_US_SERVO, MAX_US_SERVO],
                                    ang_range=[MIN_DIST_SERVO, MAX_DIST_SERVO])

    # Add motors
    self.MotorWalk = DCMotor(self._motorDriver, drv8835.MOTOR_A)
    self.MotorTurn = DCMotor(self._motorDriver, drv8835.MOTOR_B)

    if BOARD_VER >= 120 and USE_LOAD_SENSING:
      # Create filters to smooth the load readings from the motors and change
      # analog sensor update mask accordingly
      self.walkLoadFilter = TemporalFilter(5)
      self.turnLoadFilter = TemporalFilter(5)
      self._MCP3208.channelMask |= 0xC0

    # Flag that indicates when the robot should stop moving
    self.onHold = False

    # If to use compass, initialize target heading
    if USE_COMPASS:
      self._targetHead = self.Compass.getHeading()
      self._turnBias   = 0

    # Create filters for smoothing the pitch and roll readings
    self.PitchFilter = TemporalFilter(8, "f", 6)
    self.RollFilter  = TemporalFilter(8, "f", 6)

    self.tTemp = time.ticks_us()

    # Starting state
    self.state = STATE_IDLE

  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  def housekeeper(self, info=None):
    """ Does the hexbug-related housekeeping:
        - Stop motors if robot is tilted (e.g. falls on the side) by checking
          pitch/roll provided by the compass
        - Changes also color of NeoPixel depending on the robot's state
    """
    # Check if robot is tilted ...
    epr = self.Compass.getPitchRoll()
    pAv = self.PitchFilter.mean(epr[1])
    rAv = self.RollFilter.mean(epr[2])
    self.onHold = (abs(pAv) > PIRO_MAX_ANGLE) or (abs(rAv) > PIRO_MAX_ANGLE)
    if self.onHold:
      # Stop motors
      self.MotorTurn.speed = 0
      self.MotorWalk.speed = 0
      self.ServoRangingSensor.off()
      self.state = STATE_ON_HOLD

    if USE_LOAD_SENSING:
      wAv = self.walkLoadFilter.mean(self._MCP3208.data[6])
      tAv = self.turnLoadFilter.mean(self._MCP3208.data[7])
      print("[{0:30}] [{1:30}]".format("*" *int(wAv/30), "#" *int(tAv/30)))

    # Change NeoPixel according to state
    i = self.state *3
    self.startPulseNeoPixel(STATE_COLORS[i:i+3])

  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  def onLoopStart(self):
    """ To measure the performance of the loops, call this function once at
        the beginning of the main loop
    """
    pass

  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  def scanForObstacleOrCliff(self):
    """ Acquires distance data at the scan positions, currently given in motor
        run time (in [s]). Returns -1=obstacle, 1=cliff, and 0=none.
    """
    # If compass is used, determine current offset from target heading and
    # set a new bias (in [ms]) by which the head position is corrected. This
    # is done by biasing the turning time when scanning for obstacles
    if USE_COMPASS:
      dh = self.Compass.getHeading() -self._targetHead
      if abs(dh) > HEAD_ADJUST_THR:
        self._turnBias = dh *HEAD_ADJUST_FACT

    o = False
    c = False
    for iPos, Pos in enumerate(self._scanPos):
      bias = self._turnBias if USE_COMPASS else 0
      self.MotorTurn.speed = SPEED_SCAN *(-1,1)[Pos < 0]
      self.spin_ms(abs(Pos) +bias)
      self.MotorTurn.speed = 0
      self.spin_ms(10)
      d = self.RangingSensor.range_cm
      self._distData[iPos] = d
      o = o or (d < DIST_OBST_CM)
      c = c or (d > DIST_CLIFF_CM)

    if USE_COMPASS:
      print(bias, self._targetHead)
      # ...
    return 1 if c else -1 if o else 0


  def lookAround(self):
    """ Make an appearance of "looking around"
    """
    # Stop all motors and change state
    self.MotorWalk.speed = 0
    self.MotorTurn.speed = 0
    prevState  = self.state
    self.state = STATE_LOOKING
    maxPit = max(MAX_DIST_SERVO, MIN_DIST_SERVO)

    # Move head and IR distance sensor at random, as if looking around
    nSacc = random.randint(4, 10)
    yaw   = 0
    pit   = SCAN_DIST_SERVO
    try:
      for i in range(nSacc):
        if self.onHold:
          break
        dYaw = random.randint(-800, 800)
        yaw += dYaw
        dir  = -1 if dYaw < 0 else 1
        pit += random.randint(-10,15)
        pit  = min(max(0, pit), maxPit)
        self.ServoRangingSensor.angle = pit
        self.MotorTurn.speed = SPEED_TURN *dir
        self.spin_ms(abs(dYaw))
        self.MotorTurn.speed = 0
        self.spin_ms(random.randint(0, 500))

    finally:
      # Stop head movement, if any, move the IR sensor back into scan
      # position and change back state
      self.MotorTurn.speed = 0
      self.ServoRangingSensor.angle = SCAN_DIST_SERVO
      self.state = prevState

      # If compass is used, set new target heading
      if USE_COMPASS:
        self._targetHead = self.Compass.getHeading()

  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  def getDist(self, angle=0, trials=1):
    """ Test function to determine the relevant IR distances.
        Moves IR ranging sensor to "angle" and measures/prints distance
        "trial" times.
    """
    self.ServoRangingSensor.angle = angle
    self.spin_ms(200)
    for i in range(trials):
      self.update()
      print("{0} cm".format(self.RangingSensor.range_cm))
      self.spin_ms(0 if trials <= 1 else 250)

# ----------------------------------------------------------------------------
