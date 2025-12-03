# Cooking Game – CircuitPython Motion Game

## 1. Overview

**Cooking Game** is a small motion-based game built with CircuitPython.  
The player follows a simple “recipe” made of four actions:

- **ADD** – press the button to add ingredients  
- **MIX** – shake the device  
- **HEAT** – turn the rotary encoder to set the correct heat level  
- **TILT** – tilt and hold the device to pour

Each level gives the player a sequence of these actions.  
If the player performs the correct action in time, they earn points and move to the next step.  
If they shake at the wrong time or run out of time, the game ends.

When the board powers on, the game shows:

1. **Splash Screen** – animated boiling pot and “COOKING GAME” title  
2. **Menu Screen** – choose difficulty with the rotary encoder  
3. **Gameplay Screen** – follow the step instructions and finish the recipe


## 2. Hardware Used

- **Microcontroller**: Adafruit Feather / Xiao ESP32-C3 (CircuitPython board)
- **Display**: 128×64 I2C OLED (SSD1306)
- **Motion Sensor**: ADXL345 accelerometer (I2C)
- **Rotary Encoder** (2 pins + GND)
- **NeoPixel** (1 LED) on pin D0  
- **Power**: USB or LiPo battery
- Perfboard + jumper wires

> Pin mapping (as used in `code.py`)
- **Rotary A** → D1  
- **Rotary B** → D2  
- **Button** → D9  
- **NeoPixel** → D0  
- **OLED + ADXL345** → I2C (SDA, SCL, 3V, GND)



## 3. Required Libraries

All libraries live in the `lib/` folder on the board and in this repo.

This project uses:

- `adafruit_displayio_ssd1306`
- `adafruit_display_text`
- `adafruit_adxl34x`
- `adafruit_debouncer`
- `adafruit_bitmap_font`
- `neopixel`
- `i2cdisplaybus`
- `rainbowio` (built-in on many CircuitPython builds)

The `lib/` folder in this repo contains the minimal set of `.mpy` files required for the game to run.



## 4. How the Game Works

### 4.1 Game Flow

1. **Splash Screen**
   - Shows a simple pixel-art pot with a lid.
   - Steam and lid are slightly animated to look like boiling.
   - Retro “COOKING / GAME” title uses a bitmap font.

2. **Menu / Difficulty Selection**
   - Title: “COOKING GAME”
   - Use the rotary encoder to move the highlight bar:
     - `EASY`
     - `NORMAL`
     - `HARD`
   - Press the button to start the game with the selected difficulty.

3. **Gameplay**
   - A recipe is a list of actions: `ADD`, `MIX`, `HEAT`, `TILT`.
   - The OLED shows:
     - Current mode (EASY / NORMAL / HARD)
     - Step number (`STEP x / total`)
     - Instruction (`DO: MIX`, `DO: HEAT`, etc.)
     - Current score
   - If the player performs the correct action:
     - Score increases (higher difficulty → more points)
     - Next step starts
   - If the player runs out of time or makes a wrong move:
     - Game over screen is shown

4. **End of Game**
   - **Win**: player finishes all steps in the recipe  
     → “YOU WIN!” + rainbow NeoPixel animation  
   - **Lose**: timeout or wrong move  
     → “GAME OVER!” + red flash on NeoPixel  
   - Press the button to return to the menu.


### 4.2 Controls and Sensing

- **ADD**
  - Press the button once.
  - On Normal/Hard, a strong shake during ADD counts as a **wrong move** and ends the game.

- **MIX**
  - Shake the device.
  - The code looks for multiple acceleration spikes over a short time window to detect mixing.

- **HEAT**
  - Turn the rotary encoder to set **LOW / MID / HIGH**.
  - When the encoder matches the target heat and is held for a short time:
    - Step is cleared.
  - A NeoPixel color shows the current heat level:
    - OFF → none
    - Blue → LOW
    - Orange → MID
    - Pink → HIGH

- **TILT**
  - Tilt and hold the device to one side.
  - The ADXL345 `x` value must stay above a threshold long enough to count.

---

### 4.3 Difficulty & Scoring

- **EASY**
  - Longer time limit per step.
  - No penalty for shaking during ADD.
  - +10 points per correct step.

- **NORMAL**
  - Shorter time limit.
  - Strong shaking during ADD → immediate GAME OVER.
  - +15 points per correct step.

- **HARD**
  - Fastest time limit and longer recipes.
  - Same wrong-shake rule as NORMAL.
  - +20 points per correct step.


## 5. System Diagram

The repo includes an image that shows the high-level system:

- Inputs: rotary encoder, button, accelerometer
- Processing: main game loop on the microcontroller
- Outputs: OLED display, NeoPixel LED
- Power: USB or battery

System diagram file :

```text
Documentation/"System Block Diagram.png"
```


## 6. Circuit Diagram

The repo also includes a circuit / wiring diagram that shows:

* I2C wiring for OLED + ADXL345
* Rotary encoder pins to D1/D2 and GND
* Button to D9 and GND (with internal pull-up)
* NeoPixel on D0 with 3V and GND
* Power rails on the breadboard

Example file:

```text
Documentation/final_project.kicad_sch
```


## 7. Enclosure Design

The enclosure is designed to support **motion-based gameplay**, not just a bare breadboard.

Design goals:

* Make the device feel like a small **cooking-themed handheld**:

  * Clear window for the OLED so the pot and cooking UI are visible.
  * Easy access to the rotary encoder (like a knob for controlling heat).

* Allow comfortable **shaking and tilting**:

  * Shape and size that can be held in one hand.
  * Components placed so the board is balanced while shaking.
* Fabrication method:

  * Laser-cut enclosure so it’s quick to prototype and easy to assemble.
  * Screw holes / tabs for mounting the PCB and securing the OLED.



## 8. File Structure


```text
.
├── code.py                     # main game code
├── README.md                   # this file
├── Documents
│   ├── System Block Diagram.png
│   ├── final_project_diagrams.pdf    
│   └── final_project.kicad_sch
└── lib
    ├── adafruit_displayio_ssd1306.mpy
    ├── adafruit_display_text
    ├── adafruit_adxl34x.mpy
    ├── adafruit_debouncer.mpy
    ├── adafruit_bitmap_font
    ├── i2cdisplaybus.mpy
    ├── neopixel.mpy
    └── ---
```


## 9. How to Run

1. Install CircuitPython on the board used in class.
2. Copy `code.py` and the `lib/` folder from this repo onto the CIRCUITPY drive.
3. Connect the hardware according to the circuit diagram.
4. Press reset or power the board.
5. When the splash screen appears:

   * Use the encoder to choose a difficulty.
   * Press the button to start cooking!

```

TECHIN 512 – Final Project
