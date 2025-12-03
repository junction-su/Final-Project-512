import time
import board
import digitalio
from adafruit_debouncer import Debouncer
import displayio
from i2cdisplaybus import I2CDisplayBus
import adafruit_displayio_ssd1306
import adafruit_adxl34x
from adafruit_display_text import label
import terminalio
import neopixel
import rainbowio
from adafruit_bitmap_font import bitmap_font
from adafruit_display_shapes.rect import Rect  # (unused, but kept here in case of future UI tweaks)


# ===================== Common setup (OLED + I2C + Accelerometer) =====================

displayio.release_displays()
i2c = board.I2C()

display_bus = I2CDisplayBus(i2c, device_address=0x3C)
oled = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

root = displayio.Group()
oled.root_group = root

accel = adafruit_adxl34x.ADXL345(i2c)


# ===================== Rotary Encoder =====================

enc_a = digitalio.DigitalInOut(board.D1)
enc_a.direction = digitalio.Direction.INPUT
enc_a.pull = digitalio.Pull.UP

enc_b = digitalio.DigitalInOut(board.D2)
enc_b.direction = digitalio.Direction.INPUT
enc_b.pull = digitalio.Pull.UP

enc_a_db = Debouncer(enc_a, interval=0.002)
enc_b_db = Debouncer(enc_b, interval=0.002)

enc_pos = 0
heat_start_pos = 0


def update_encoder():
    """Update encoder debouncers and track a simple position counter."""
    global enc_pos
    enc_a_db.update()
    enc_b_db.update()

    if enc_a_db.fell:
        if enc_b_db.value:
            enc_pos += 1   # clockwise
        else:
            enc_pos -= 1   # counter-clockwise


# ===================== Button =====================

btn = digitalio.DigitalInOut(board.D9)
btn.direction = digitalio.Direction.INPUT
btn.pull = digitalio.Pull.UP
last_btn_value = True


# ===================== Accelerometer (MIX / TILT) =====================

last_mag = 0.0
last_shake_ms = 0
last_tilt_ms = 0

mix_spike_count = 0
mix_spike_window_ms = 250
last_mix_spike_ms = 0

SHAKE_THRESHOLD = 5.5
TILT_THRESHOLD = 6.5
COOLDOWN_MS = 800

ACTION_LOCK_MS = 400
last_action_ms = 0

tilt_hold_start_ms = 0
tilt_hold_active = False

last_step_change_ms = 0


# ===================== Game constants =====================

ACTION_ADD = 0
ACTION_MIX = 1
ACTION_HEAT = 2
ACTION_TILT = 3

STATE_MENU = 0
STATE_PLAYING = 1
STATE_GAME_OVER = 2
STATE_GAME_WIN = 3

DIFFICULTY_EASY = 0
DIFFICULTY_NORMAL = 1
DIFFICULTY_HARD = 2
DIFFICULTY_NAMES = ["EASY", "NORMAL", "HARD"]

MENU_TICKS_PER_STEP = 2


# ===================== HEAT constants =====================

HEAT_NONE = -1
HEAT_LOW = 0
HEAT_MID = 1
HEAT_HIGH = 2
HEAT_NAMES = ["LOW", "MID", "HIGH"]

HEAT_TICKS_REQUIRED = 1
HEAT_TIMEOUT_MS = 9000
HEAT_HOLD_MS = 1200
HEAT_DRAW_THROTTLE_MS = 120
HEAT_CLEAR_SHOW_MS = 2500

heat_target = HEAT_MID
heat_level = HEAT_NONE
heat_moved = False

heat_holding = False
heat_hold_start_ms = 0

heat_last_draw_ms = 0
heat_just_cleared = False
heat_clear_ms = 0


# ===================== NeoPixel =====================

PIXEL_PIN = board.D0          # external NeoPixel pin
NUM_PIXELS = 1
pixels = neopixel.NeoPixel(PIXEL_PIN, NUM_PIXELS, brightness=0.3, auto_write=False)


def pixels_off():
    pixels.fill((0, 0, 0))
    pixels.show()


def set_heat_led(level):
    """Map HEAT level to NeoPixel color."""
    if level == HEAT_NONE:
        pixels.fill((0, 0, 0))          # off
    elif level == HEAT_LOW:
        pixels.fill((0, 0, 255))        # blue (low heat)
    elif level == HEAT_MID:
        pixels.fill((255, 180, 0))      # orange (medium)
    elif level == HEAT_HIGH:
        pixels.fill((179, 46, 46))      # red (high)
    pixels.show()


def rainbow_spin(duration_ms=1200, step_ms=20):
    """Short rainbow spin effect for win screen."""
    start = now_ms()
    hue = 0
    while now_ms() - start < duration_ms:
        c = rainbowio.colorwheel(hue & 255)
        pixels.fill(c)
        pixels.show()
        hue += 5
        time.sleep(step_ms / 1000)


def flash_color(color, duration_ms=600):
    """Flash a single color for a moment."""
    pixels.fill(color)
    pixels.show()
    time.sleep(duration_ms / 1000)
    pixels_off()


# ===================== Global game state & score =====================

state = STATE_MENU
difficulty = DIFFICULTY_EASY

current_step = 0
recipe = []
move_start_ms = 0
time_limit_ms = 5000

menu_index = 0
last_menu_pos = 0

score = 0  # player score


# ===== Retro font for splash title =====
league_font = bitmap_font.load_font("/fonts/LeagueSpartan-Bold-16.bdf")


# ===================== Utility =====================

def now_ms():
    return time.monotonic_ns() // 1_000_000


def action_name(action):
    return ["ADD", "MIX", "HEAT", "TILT"][action]


def draw_screen(lines):
    """
    Clear the OLED and draw up to 4 lines of centered text
    using the default terminal font.
    """
    global root
    root = displayio.Group()
    oled.root_group = root

    # clear background
    bg_bitmap = displayio.Bitmap(128, 64, 1)
    bg_palette = displayio.Palette(1)
    bg_palette[0] = 0x000000
    bg_tile = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette, x=0, y=0)
    root.append(bg_tile)

    y = 12
    for t in lines[:4]:
        text = str(t)

        # approximate width assuming ~6 px per character
        text_width = len(text) * 6
        x = (128 - text_width) // 2
        if x < 0:
            x = 0  # if too long, left-align

        lbl = label.Label(terminalio.FONT, text=text, color=0xFFFFFF, x=x, y=y)
        root.append(lbl)
        y += 14


def make_pot_sprite():
    """
    Simple 32x32 bitmap with a pot + lid.
    Currently unused, but kept as a utility if needed.
    """
    pot_bitmap = displayio.Bitmap(32, 32, 2)
    pot_palette = displayio.Palette(2)
    pot_palette[0] = 0x000000  # background
    pot_palette[1] = 0xFFFFFF  # pot color

    # pot body (x: 4–27, y: 16–26)
    for y in range(16, 27):
        for x in range(4, 28):
            pot_bitmap[x, y] = 1

    # top rim
    for x in range(4, 28):
        pot_bitmap[x, 15] = 1

    # side handles
    for y in range(18, 22):
        pot_bitmap[2, y] = 1
        pot_bitmap[29, y] = 1

    # lid body (x: 8–23, y: 11–14)
    for y in range(11, 15):
        for x in range(8, 24):
            pot_bitmap[x, y] = 1

    # lid handle
    for y in range(8, 11):
        for x in range(14, 18):
            pot_bitmap[x, y] = 1

    pot_tile = displayio.TileGrid(pot_bitmap, pixel_shader=pot_palette, x=48, y=8)
    return pot_tile


# ===================== Splash screen =====================

def show_splash():
    """
    Animated splash screen:
    - boiling pot + lid jiggle
    - retro 'COOKING' / 'GAME' title text
    """
    global root
    root = displayio.Group()
    oled.root_group = root

    # background
    bg_bitmap = displayio.Bitmap(128, 64, 1)
    bg_palette = displayio.Palette(1)
    bg_palette[0] = 0x000000
    bg_tile = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette, x=0, y=0)
    root.append(bg_tile)

    # --- pot body (slightly higher to leave room for title) ---
    pot_w = 32
    pot_h = 14
    pot_bitmap = displayio.Bitmap(pot_w, pot_h, 2)
    pot_palette = displayio.Palette(2)
    pot_palette[0] = 0x000000  # transparent/background
    pot_palette[1] = 0xFFFFFF  # pot color

    # body
    for y in range(6, pot_h):
        for x in range(2, pot_w - 2):
            pot_bitmap[x, y] = 1
    # top line
    for x in range(0, pot_w):
        pot_bitmap[x, 5] = 1

    pot_x = (128 - pot_w) // 2
    pot_y = 14

    pot_tile = displayio.TileGrid(
        pot_bitmap,
        pixel_shader=pot_palette,
        x=pot_x,
        y=pot_y,
    )
    root.append(pot_tile)

    # --- lid (slightly resting on top) ---
    lid_w = 24
    lid_h = 5
    lid_bitmap = displayio.Bitmap(lid_w, lid_h, 2)
    lid_palette = displayio.Palette(2)
    lid_palette[0] = 0x000000
    lid_palette[1] = 0xFFFFFF

    # lid body
    for y in range(2, lid_h):
        for x in range(0, lid_w):
            lid_bitmap[x, y] = 1
    # knob
    lid_bitmap[lid_w // 2, 0] = 1
    lid_bitmap[lid_w // 2, 1] = 1

    lid_base_x = pot_x + 4
    lid_base_y = pot_y - 3

    lid_tile = displayio.TileGrid(
        lid_bitmap,
        pixel_shader=lid_palette,
        x=lid_base_x,
        y=lid_base_y,
    )
    root.append(lid_tile)

    # --- steam blobs ---
    steam_bitmap = displayio.Bitmap(3, 3, 2)
    steam_palette = displayio.Palette(2)
    steam_palette[0] = 0x000000
    steam_palette[1] = 0xFFFFFF

    for y in range(3):
        for x in range(3):
            steam_bitmap[x, y] = 1

    steam1 = displayio.TileGrid(
        steam_bitmap,
        pixel_shader=steam_palette,
        x=pot_x + 8,
        y=pot_y - 10,
    )
    steam2 = displayio.TileGrid(
        steam_bitmap,
        pixel_shader=steam_palette,
        x=pot_x + pot_w - 11,
        y=pot_y - 7,
    )
    root.append(steam1)
    root.append(steam2)

    # --- title text ('COOKING' / 'GAME') ---
    title1 = label.Label(
        league_font,
        text="COOKING",
        color=0xFFFFFF,
    )
    title1.anchor_point = (0.5, 0.5)            # centered
    title1.anchored_position = (64, 40)         # slightly above center

    title2 = label.Label(
        league_font,
        text="GAME",
        color=0xFFFFFF,
    )
    title2.anchor_point = (0.5, 0.5)
    title2.anchored_position = (64, 54)         # a bit below COOKING

    root.append(title1)
    root.append(title2)

    # --- animation loop (lid jiggle + steam drift) ---
    start = time.monotonic()
    frame = 0
    while time.monotonic() - start < 2.0:  # ~2 seconds
        # lid jiggle
        lid_tile.y = lid_base_y - (frame % 2)

        # steam moves up a bit
        steam1.y = (pot_y - 10) - (frame % 4)
        steam2.y = (pot_y - 7) - ((frame + 2) % 4)

        frame += 1
        time.sleep(0.06)


# ===================== Recipes =====================

def make_easy_recipe():
    return [
        ACTION_ADD, ACTION_ADD, ACTION_ADD,
        ACTION_HEAT,
        ACTION_MIX, ACTION_TILT,
        ACTION_ADD, ACTION_MIX, ACTION_TILT, ACTION_ADD
    ]


def make_normal_recipe():
    return [
        ACTION_ADD, ACTION_ADD, ACTION_MIX,
        ACTION_HEAT,
        ACTION_TILT, ACTION_ADD, ACTION_MIX,
        ACTION_HEAT,
        ACTION_TILT, ACTION_MIX, ACTION_ADD, ACTION_MIX
    ]


def make_hard_recipe():
    return [
        ACTION_ADD, ACTION_MIX, ACTION_ADD,
        ACTION_HEAT,
        ACTION_TILT, ACTION_TILT, ACTION_MIX, ACTION_ADD,
        ACTION_HEAT,
        ACTION_MIX, ACTION_TILT,
        ACTION_HEAT,
        ACTION_ADD, ACTION_MIX, ACTION_TILT
    ]


# ===================== Input handling =====================

def get_player_action(expected_action):
    """
    Read player input according to the expected action for this step.

    ADD:
        - Normal/Hard only: strong shake is treated as WRONG_SHAKE.
        - Button press is a correct ADD.

    MIX:
        - Multiple strong shakes within a time window.

    HEAT:
        - Use encoder to reach LOW/MID/HIGH and hold the target level.

    TILT:
        - Tilt and hold for a short period.
    """
    global last_btn_value, last_mag, last_shake_ms, last_tilt_ms
    global tilt_hold_start_ms, tilt_hold_active, last_action_ms
    global heat_start_pos, heat_level, heat_target, heat_moved
    global heat_holding, heat_hold_start_ms, heat_last_draw_ms
    global heat_just_cleared, heat_clear_ms
    global mix_spike_count, last_mix_spike_ms
    global move_start_ms

    now = now_ms()

    # --------------------- ADD ---------------------
    if expected_action == ACTION_ADD:
        # correct: button pressed
        current_btn = btn.value
        if last_btn_value and (current_btn is False):
            last_btn_value = current_btn
            last_action_ms = now
            return ACTION_ADD
        last_btn_value = current_btn

        # only punish shaking in Normal / Hard
        if difficulty != DIFFICULTY_EASY:
            # ignore right after step change
            if now - move_start_ms < 600:
                return None

            x, y, z = accel.acceleration
            mag = (x * x + y * y + z * z) ** 0.5

            if last_mag == 0.0:
                last_mag = mag
                return None

            delta_mag = abs(mag - last_mag)
            last_mag = mag

            if delta_mag > SHAKE_THRESHOLD:
                last_action_ms = now
                return "WRONG_SHAKE"

        return None

    # --------------------- HEAT ---------------------
    if expected_action == ACTION_HEAT:
        if now - last_action_ms < ACTION_LOCK_MS:
            return None

        delta = enc_pos - heat_start_pos
        prev_level = heat_level

        # encoder → heat level mapping
        if not heat_moved:
            if abs(delta) < HEAT_TICKS_REQUIRED:
                heat_level = HEAT_NONE
            elif delta < 0:
                heat_level = HEAT_LOW
                heat_moved = True
            else:
                heat_level = HEAT_HIGH
                heat_moved = True
        else:
            if delta <= -HEAT_TICKS_REQUIRED:
                heat_level = HEAT_LOW
            elif delta >= HEAT_TICKS_REQUIRED:
                heat_level = HEAT_HIGH
            else:
                heat_level = HEAT_MID

        # update LED by heat level
        set_heat_led(heat_level)

        # update OLED only when level actually changes (with throttle)
        if heat_level != prev_level and (now - heat_last_draw_ms > HEAT_DRAW_THROTTLE_MS):
            heat_last_draw_ms = now
            now_txt = "--" if heat_level == HEAT_NONE else HEAT_NAMES[heat_level]
            draw_screen([
                f"{DIFFICULTY_NAMES[difficulty]} MODE",
                f"STEP {current_step + 1}/{len(recipe)}",
                f"SET HEAT: {HEAT_NAMES[heat_target]}",
                f"NOW: {now_txt}",
            ])

        # check if target level is reached and held
        if heat_level == heat_target and heat_level != HEAT_NONE:
            if not heat_holding:
                heat_holding = True
                heat_hold_start_ms = now
                draw_screen([
                    f"{DIFFICULTY_NAMES[difficulty]} MODE",
                    f"STEP {current_step + 1}/{len(recipe)}",
                    "HOLD HEAT...",
                    f"NOW: {HEAT_NAMES[heat_level]}",
                ])
            else:
                if now - heat_hold_start_ms >= HEAT_HOLD_MS:
                    heat_just_cleared = True
                    heat_clear_ms = now
                    draw_screen([
                        f"{DIFFICULTY_NAMES[difficulty]} MODE",
                        f"STEP {current_step + 1}/{len(recipe)}",
                        "HEAT OK!",
                        f"{HEAT_NAMES[heat_level]} matched",
                    ])
                    last_action_ms = now
                    heat_holding = False
                    return ACTION_HEAT
        else:
            heat_holding = False

        # timeout for HEAT if player never reaches target
        if now - move_start_ms > HEAT_TIMEOUT_MS:
            return "TIMEOUT_HEAT"

        return None

    # --------------------- Common accel path (MIX / TILT) ---------------------
    if now - last_action_ms < ACTION_LOCK_MS:
        return None

    x, y, z = accel.acceleration
    mag = (x * x + y * y + z * z) ** 0.5
    delta_mag = abs(mag - last_mag)
    last_mag = mag

    # --------------------- MIX ---------------------
    if expected_action == ACTION_MIX:
        # need multiple strong spikes in a short time
        if delta_mag > SHAKE_THRESHOLD:
            if now - last_mix_spike_ms < mix_spike_window_ms:
                mix_spike_count += 1
            else:
                mix_spike_count = 1
            last_mix_spike_ms = now

            if mix_spike_count >= 2 and (now - last_shake_ms > COOLDOWN_MS):
                mix_spike_count = 0
                last_shake_ms = now
                last_action_ms = now
                tilt_hold_active = False
                tilt_hold_start_ms = 0
                return ACTION_MIX
        return None

    # --------------------- TILT ---------------------
    if expected_action == ACTION_TILT:
        if abs(x) > TILT_THRESHOLD:
            if not tilt_hold_active:
                tilt_hold_active = True
                tilt_hold_start_ms = now
            else:
                if (now - tilt_hold_start_ms > 400) and (now - last_tilt_ms > COOLDOWN_MS):
                    last_tilt_ms = now
                    last_action_ms = now
                    tilt_hold_active = False
                    tilt_hold_start_ms = 0
                    return ACTION_TILT
        else:
            tilt_hold_active = False
            tilt_hold_start_ms = 0
        return None

    return None


# ===================== Screens =====================

def show_menu():
    """Difficulty selection screen with highlight bar."""
    global root
    root = displayio.Group()
    oled.root_group = root

    pixels_off()  # always off in menu

    # background
    bg_bitmap = displayio.Bitmap(128, 64, 1)
    bg_palette = displayio.Palette(1)
    bg_palette[0] = 0x000000
    bg_tile = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette, x=0, y=0)
    root.append(bg_tile)

    # centered title
    title = label.Label(
        terminalio.FONT,
        text="COOKING GAME",
        color=0xFFFFFF,
    )
    title.anchor_point = (0.5, 0.0)      # center horizontally, top vertically
    title.anchored_position = (64, 6)
    root.append(title)

    # difficulty options
    options = ["EASY", "NORMAL", "HARD"]

    base_y = 26
    line_gap = 16

    for idx, text in enumerate(options):
        line_y = base_y + idx * line_gap
        selected = (idx == menu_index)

        bar_w = 110
        bar_h = 12

        bar_x = (128 - bar_w) // 2
        bar_y = line_y - 6

        if selected:
            # filled white bar with black text
            bar_bitmap = displayio.Bitmap(bar_w, bar_h, 1)
            bar_palette = displayio.Palette(1)
            bar_palette[0] = 0xFFFFFF

            for yy in range(bar_h):
                for xx in range(bar_w):
                    bar_bitmap[xx, yy] = 0

            bar_tile = displayio.TileGrid(
                bar_bitmap,
                pixel_shader=bar_palette,
                x=bar_x,
                y=bar_y
            )
            root.append(bar_tile)
            text_color = 0x000000
        else:
            text_color = 0xFFFFFF

        text_width = len(text) * 6
        text_x = (128 - text_width) // 2

        lbl = label.Label(
            terminalio.FONT,
            text=text,
            color=text_color,
            x=text_x,
            y=line_y
        )
        root.append(lbl)


def show_current_step():
    """Step UI while playing: action + score (or HEAT prompt)."""
    global heat_start_pos, heat_target, heat_level, heat_moved
    global heat_holding, heat_hold_start_ms, heat_last_draw_ms

    step_num = current_step + 1
    total = len(recipe)
    action = recipe[current_step]
    act_txt = action_name(action)

    print(f"[STEP {step_num}/{total}] DO: {act_txt}")

    if action == ACTION_HEAT:
        heat_start_pos = enc_pos
        heat_target = (now_ms() // 1000) % 3  # rotate target
        heat_level = HEAT_NONE
        heat_moved = False

        heat_holding = False
        heat_hold_start_ms = 0
        heat_last_draw_ms = 0

        set_heat_led(HEAT_NONE)

        draw_screen([
            f"{DIFFICULTY_NAMES[difficulty]} MODE",
            f"STEP {step_num}/{total}",
            "DO: HEAT",
            f"SET HEAT: {HEAT_NAMES[heat_target]}",
        ])
    else:
        set_heat_led(HEAT_NONE)
        draw_screen([
            f"{DIFFICULTY_NAMES[difficulty]} MODE",
            f"STEP {step_num}/{total}",
            f"DO: {act_txt}",
            f"SCORE: {score}",
        ])


def show_game_over(reason=""):
    draw_screen([
        "GAME OVER!",
        str(reason)[:18],
        f"SCORE: {score}",
        "BTN: Menu",
    ])
    flash_color((255, 0, 0), 800)


def show_game_win():
    draw_screen([
        "YOU WIN!",
        "Cooking done :)",
        f"SCORE: {score}",
        "BTN: Menu",
    ])
    rainbow_spin(3000)
    pixels_off()


# ===================== State transitions =====================

def start_game(selected):
    """Initialize a new game for the chosen difficulty."""
    global state, difficulty, recipe, current_step
    global move_start_ms, time_limit_ms, last_step_change_ms, score

    difficulty = selected

    if difficulty == DIFFICULTY_EASY:
        recipe = make_easy_recipe()
        time_limit_ms = 5000
    elif difficulty == DIFFICULTY_NORMAL:
        recipe = make_normal_recipe()
        time_limit_ms = 4000
    else:
        recipe = make_hard_recipe()
        time_limit_ms = 3000

    current_step = 0
    score = 0
    state = STATE_PLAYING
    move_start_ms = now_ms()
    last_step_change_ms = move_start_ms

    print(f"\n=== START {DIFFICULTY_NAMES[difficulty]} ===")
    show_current_step()


def update_playing():
    """Main per-frame update while the game is in PLAYING state."""
    global current_step, move_start_ms, state, last_step_change_ms
    global last_mag, heat_just_cleared, heat_clear_ms, score

    update_encoder()
    now = now_ms()

    # keep HEAT OK screen visible for a short time
    if heat_just_cleared:
        if now - heat_clear_ms < HEAT_CLEAR_SHOW_MS:
            return
        heat_just_cleared = False
        move_start_ms = now
        last_step_change_ms = now

    expected = recipe[current_step]

    # generic timeout (HEAT has its own)
    if expected != ACTION_HEAT:
        if now - move_start_ms > time_limit_ms:
            state = STATE_GAME_OVER
            show_game_over("TIME OUT")
            return

    # ignore sensor noise right after a step change
    if now - last_step_change_ms < 200:
        return

    action = get_player_action(expected)

    if action is None:
        return

    if action == "TIMEOUT_HEAT":
        state = STATE_GAME_OVER
        show_game_over("HEAT TIMEOUT")
        return

    # Normal / Hard only: shaking during ADD is a wrong move
    if difficulty != DIFFICULTY_EASY and action == "WRONG_SHAKE":
        state = STATE_GAME_OVER
        show_game_over("WRONG MOVE")
        return

    # correct move → give score
    if difficulty == DIFFICULTY_EASY:
        score += 10
    elif difficulty == DIFFICULTY_NORMAL:
        score += 15
    else:
        score += 20

    current_step += 1

    if current_step >= len(recipe):
        state = STATE_GAME_WIN
        show_game_win()
        return

    move_start_ms = now
    last_step_change_ms = now

    # reset accel baseline
    x, y, z = accel.acceleration
    last_mag = (x * x + y * y + z * z) ** 0.5

    show_current_step()


# ===================== Main loop =====================

print("Booting Cooking Game...")
show_splash()
show_menu()

while True:
    if state == STATE_MENU:
        update_encoder()

        step = enc_pos // MENU_TICKS_PER_STEP
        if step != last_menu_pos:
            if step > last_menu_pos:
                menu_index = (menu_index + 1) % 3
            else:
                menu_index = (menu_index - 1) % 3
            last_menu_pos = step
            show_menu()

        if not btn.value:
            while not btn.value:
                time.sleep(0.05)
            start_game(menu_index)

    elif state == STATE_PLAYING:
        update_playing()

    elif state in (STATE_GAME_OVER, STATE_GAME_WIN):
        if not btn.value:
            while not btn.value:
                time.sleep(0.05)
            state = STATE_MENU
            show_menu()

    time.sleep(0.01)
