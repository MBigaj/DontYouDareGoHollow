"""The game's sound effects: recorded CC0 sources (source/, see LICENSE.md) layered with sounds
synthesised here, mixed and written as small MP3s for the browser.

The split follows the art: recordings where the world makes the sound (a blade, a punch, an
anvil, coins, footsteps, a bell), synthesis for what nothing recorded covers (fire catching,
fog, souls, a boss falling) and for the quiet ticks of a lesson, which must stay soft and short.
The big moments run through a little reverb, as if in a stone hall.

Each sound has a level (its peak, 0..1) so a lesson tick stays far below a felled boss. Names
with a _<n> suffix are variants; the page picks one at random. Deterministic: seeded noise,
bit-exact encoding, so running it again rewrites the same files.

Usage:
  uv run --with numpy --with scipy python tools/sounds/sounds.py \\
      src/hollow/adapters/web/static/sounds
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

HERE = Path(__file__).parent
SRC = HERE / "source"
RATE = 44100
Wave = np.ndarray


# ---------------------------------------------------------------- building blocks
def load(name: str) -> Wave:
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(SRC / name), "-f", "f32le",
                          "-ac", "1", "-ar", str(RATE), "-"],
                         capture_output=True, check=True).stdout  # fmt: skip
    x = np.frombuffer(raw, np.float32).astype(float)
    return x / max(np.abs(x).max(), 1e-9)


def times(seconds: float) -> Wave:
    return np.arange(int(seconds * RATE)) / RATE


def env(seconds: float, attack: float, decay: float) -> Wave:
    """Linear attack, then an exponential fall to -60 dB over `decay` seconds."""
    t = times(seconds)
    rise = np.clip(t / max(attack, 1e-4), 0, 1)
    fall = np.exp(-6.9 * np.clip(t - attack, 0, None) / decay)
    return rise * fall


def noise(seconds: float, seed: int) -> Wave:
    return np.random.default_rng(seed).uniform(-1, 1, int(seconds * RATE))


def lowpass(x: Wave, hz: float, order: int = 2) -> Wave:
    return sosfilt(butter(order, hz, "low", fs=RATE, output="sos"), x)


def highpass(x: Wave, hz: float) -> Wave:
    return sosfilt(butter(2, hz, "high", fs=RATE, output="sos"), x)


def sweep(x: Wave, start: float, peak: float, end: float, at: float, poles: int = 2) -> Wave:
    """A lowpass whose cutoff rises from start to peak (at `at` of the way) and falls to end:
    fire catching, fog rolling. Each pole adds 6 dB per octave; white noise needs two."""
    for _ in range(poles):
        x = _sweep(x, start, peak, end, at)
    return x


def _sweep(x: Wave, start: float, peak: float, end: float, at: float) -> Wave:
    n = len(x)
    k = np.arange(n) / max(n - 1, 1)
    cut = np.where(k < at, start + (peak - start) * k / at, peak + (end - peak) * (k - at) / (1 - at))
    a = 1 - np.exp(-2 * np.pi * cut / RATE)
    y = np.empty(n)
    acc = 0.0
    for i in range(n):  # a few seconds of samples: fast enough in plain Python
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def tone(freq: float | Wave, seconds: float) -> Wave:
    """A sine; freq may be a per-sample array for a glide."""
    f = np.broadcast_to(np.asarray(freq, float), (int(seconds * RATE),))
    return np.sin(2 * np.pi * np.cumsum(f) / RATE)


def glide(f0: float, f1: float, seconds: float) -> Wave:
    return f0 * (f1 / f0) ** (times(seconds) / seconds)


def bell(freq: float, seconds: float) -> Wave:
    """A small struck bell: inharmonic partials, the high ones dying first."""
    out = np.zeros(int(seconds * RATE))
    for ratio, gain, decay in ((1.0, 1.0, 1.0), (2.76, 0.5, 0.5), (5.4, 0.25, 0.3), (8.93, 0.12, 0.2)):
        out += gain * tone(freq * ratio, seconds) * env(seconds, 0.002, seconds * decay)
    return out


def pitched(x: Wave, factor: float) -> Wave:
    """Play back at `factor` speed: below 1 is deeper and longer, like a bigger bell."""
    idx = np.arange(0, len(x) - 1, factor)
    return np.interp(idx, np.arange(len(x)), x)


def hall(x: Wave, seconds: float, wet: float, seed: int = 7) -> Wave:
    """Reverb from a decaying noise tail: a stone hall."""
    tail = noise(seconds, seed) * env(seconds, 0.005, seconds)
    tail = lowpass(tail, 4000)
    room = fftconvolve(x, tail)[: len(x) + len(tail)]
    room /= max(np.abs(room).max(), 1e-9)
    dry = np.concatenate([x, np.zeros(len(room) - len(x))])
    return dry * (1 - wet) + room * wet * np.abs(x).max()


def mix(*parts: tuple[float, Wave] | tuple[float, Wave, float]) -> Wave:
    """Lay parts down at their start times (seconds), each with an optional gain."""
    placed = [(int(p[0] * RATE), p[1], p[2] if len(p) > 2 else 1.0) for p in parts]
    out = np.zeros(max(at + len(w) for at, w, _ in placed))
    for at, w, gain in placed:
        out[at : at + len(w)] += w * gain
    return out


def crackle(seconds: float, count: int, seed: int) -> Wave:
    """Embers popping: short bursts of bright noise at random moments."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(seconds * RATE))
    pop = lowpass(highpass(noise(0.012, seed), 700), 3500) * env(0.012, 0.0005, 0.01)
    for at in rng.uniform(0, seconds - 0.02, count):
        i = int(at * RATE)
        out[i : i + len(pop)] += pop * rng.uniform(0.2, 1.0)
    return out


def chord(freqs: tuple[float, ...], seconds: float, attack: float, decay: float) -> Wave:
    """A soft pad: each note a sine with a quiet octave and a slow shimmer."""
    t = times(seconds)
    out = sum(tone(f, seconds) + 0.3 * tone(2 * f, seconds) for f in freqs)
    shimmer = 1 + 0.15 * np.sin(2 * np.pi * 5.5 * t)
    return out * shimmer * env(seconds, attack, decay) / len(freqs)


# ---------------------------------------------------------------- the sounds
def right() -> Wave:
    """A lesson answer right: a soft high ting."""
    return hall(mix((0, bell(1318.5, 0.4)), (0.03, bell(1975.5, 0.3), 0.35)), 0.4, 0.15)


def wrong() -> Wave:
    """A lesson answer wrong: a muted, falling thunk. Not a buzzer."""
    body = tone(glide(150, 85, 0.22), 0.22) * env(0.22, 0.004, 0.18)
    thump = lowpass(noise(0.08, 3), 400) * env(0.08, 0.001, 0.06)
    return mix((0, body), (0, thump, 0.6))


def souls() -> Wave:
    """Souls flowing in: an airy rush rising into a bright arpeggio."""
    rush = sweep(noise(0.8, 11), 300, 5000, 1500, 0.7) * env(0.8, 0.5, 0.4)
    notes = [mix((i * 0.08, bell(f, 0.9), 0.6)) for i, f in enumerate((880.0, 1108.7, 1318.5, 1760.0))]
    return hall(mix((0, rush, 0.5), *((0.35, n) for n in notes)), 1.2, 0.3)


def drop() -> Wave:
    """Titanite: two glints of glass and a high ring."""
    a, b = load("impact_glass_light_001.ogg"), pitched(load("impact_glass_light_002.ogg"), 1.25)
    return hall(mix((0, a), (0.09, b, 0.7), (0.05, bell(2637.0, 0.7), 0.25)), 0.8, 0.2)


def bonfire() -> Wave:
    """The bonfire catching: a low thump, a roar of flame and embers popping."""
    flame = sweep(noise(2.0, 21), 100, 1800, 300, 0.15) * env(2.0, 0.16, 1.7)
    thump = tone(glide(80, 45, 0.5), 0.5) * env(0.5, 0.005, 0.4)
    return hall(mix((0, thump, 0.8), (0.02, flame, 1.6), (0.25, crackle(1.8, 30, 22), 0.5)), 0.9, 0.2)


def fog() -> Wave:
    """Walking through the fog gate: a hollow rush with a low drone under it."""
    rush = sweep(noise(1.6, 31), 700, 900, 200, 0.3) * env(1.6, 0.45, 1.1)
    drone = tone(45, 1.6) * env(1.6, 0.4, 1.2)
    return hall(mix((0, rush, 1.4), (0, drone, 0.5)), 1.5, 0.35)


def strike(slice_: str, metal: str) -> Callable[[], Wave]:
    """A right answer in a fight: the blade cuts, steel bites."""

    def make() -> Wave:
        return hall(mix((0, load(slice_)), (0.035, load(metal), 0.65)), 0.5, 0.15)

    return make


def hurt() -> Wave:
    """A mistake in a fight: a heavy blow and a thud in the chest."""
    thud = tone(glide(90, 55, 0.3), 0.3) * env(0.3, 0.003, 0.25)
    return mix((0, load("impact_punch_heavy_000.ogg")), (0, thud, 0.7))


def estus() -> Wave:
    """Drinking estus: three gulps, then warmth."""
    gulp = tone(glide(320, 150, 0.08), 0.08) * env(0.08, 0.004, 0.07)
    gulp = lowpass(gulp, 900)
    warmth = chord((293.7, 440.0, 587.3, 740.0), 1.4, 0.3, 1.0)
    return hall(mix((0, gulp), (0.17, gulp, 0.9), (0.34, gulp, 0.8), (0.42, warmth, 0.6)), 1.0, 0.25)


def phase() -> Wave:
    """A boss's second wind: a deep bell tolls over a rumble."""
    toll = pitched(load("impact_bell_heavy_001.ogg"), 0.6)
    boom = tone(glide(55, 40, 1.4), 1.4) * env(1.4, 0.01, 1.2)
    rumble = lowpass(noise(1.4, 41), 180, 4) * env(1.4, 0.05, 1.2)
    return hall(mix((0, toll), (0, boom, 0.8), (0, rumble, 2.0)), 1.8, 0.35)


def felled() -> Wave:
    """A boss felled: a long boom, the great bell, and a chord rising out of the dust."""
    boom = tone(glide(62, 30, 3.2), 3.2) * env(3.2, 0.01, 3.0)
    rumble = lowpass(noise(3.0, 51), 160, 4) * env(3.0, 0.02, 2.6)
    toll = pitched(load("impact_bell_heavy_000.ogg"), 0.5)
    rise = chord((220.0, 329.6, 440.0, 554.4, 659.3), 3.2, 0.9, 2.4)
    return hall(mix((0, boom), (0, rumble, 2.2), (0.02, toll, 0.8), (0.7, rise, 0.45)), 2.4, 0.35)


def died() -> Wave:
    """Death: two low tones a semitone apart, and a bell far too deep."""
    t = times(3.6)
    organ = sum(g * np.sin(2 * np.pi * f * k * t) for f in (73.4, 77.8) for k, g in ((1, 1), (2, 0.5), (3, 0.3)))
    organ = lowpass(organ, 600) * env(3.6, 0.2, 3.2) / 3.6
    toll = pitched(load("impact_bell_heavy_001.ogg"), 0.42)
    return hall(mix((0, organ), (0.05, toll, 0.6)), 2.2, 0.35)


def anvil() -> Wave:
    """Reinforcing: three hammer blows, the last one ringing."""
    hit = load("impact_metal_heavy_000.ogg")
    ring = sum(g * tone(f, 1.2) * env(1.2, 0.002, d) for f, g, d in ((1850, 0.5, 0.9), (2930, 0.3, 0.6), (4100, 0.15, 0.4)))
    last = mix((0, load("impact_metal_heavy_001.ogg")), (0, load("impact_bell_heavy_002.ogg"), 0.4), (0, ring, 0.6))
    return hall(mix((0, hit, 0.6), (0.3, hit, 0.8), (0.6, last)), 0.7, 0.15)


def recorded(name: str) -> Callable[[], Wave]:
    def make() -> Wave:
        return load(name)

    return make


def level() -> Wave:
    """Levelling up: a rush rising into a chord, bells climbing over it."""
    rush = sweep(noise(1.0, 61), 200, 3000, 2000, 0.8) * env(1.0, 0.7, 0.4)
    pad = chord((261.6, 329.6, 392.0, 523.3), 2.0, 0.4, 1.6)
    bells = [(0.5 + i * 0.09, bell(f, 1.0), 0.4) for i, f in enumerate((523.3, 659.3, 784.0, 1046.5))]
    return hall(mix((0, rush, 0.5), (0.3, pad), *bells), 1.4, 0.3)


SOUNDS: dict[str, tuple[Callable[[], Wave], float]] = {
    # name: (maker, peak level)
    "right": (right, 0.3),
    "wrong": (wrong, 0.35),
    "souls": (souls, 0.55),
    "drop": (drop, 0.55),
    "bonfire": (bonfire, 0.8),
    "fog": (fog, 0.7),
    "strike_1": (strike("knife_slice.ogg", "impact_metal_medium_000.ogg"), 0.75),
    "strike_2": (strike("knife_slice_2.ogg", "impact_metal_heavy_000.ogg"), 0.75),
    "strike_3": (strike("knife_slice.ogg", "impact_metal_heavy_001.ogg"), 0.75),
    "hurt": (hurt, 0.8),
    "estus": (estus, 0.6),
    "phase": (phase, 0.9),
    "felled": (felled, 1.0),
    "died": (died, 0.95),
    "anvil": (anvil, 0.8),
    "coins": (recorded("handle_coins.ogg"), 0.55),
    "equip": (recorded("draw_knife_3.ogg"), 0.6),
    "level": (level, 0.7),
    "message": (recorded("book_place_1.ogg"), 0.45),
    **{f"step_{i + 1}": (recorded(f"footstep_{i}.ogg"), 0.25) for i in range(4)},
}


def finish(x: Wave, peak: float) -> Wave:
    """Trim the silent tail, fade the last 30 ms, and set the peak."""
    loud = np.where(np.abs(x) > 1e-3 * np.abs(x).max())[0]
    x = x[: loud[-1] + 1] if len(loud) else x
    fade = min(len(x), int(0.03 * RATE))
    x[-fade:] *= np.linspace(1, 0, fade)
    return x / max(np.abs(x).max(), 1e-9) * peak


def write(x: Wave, path: Path) -> None:
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-f", "s16le", "-ar", str(RATE), "-ac", "1",
                    "-i", "-", "-c:a", "libmp3lame", "-q:a", "4", "-map_metadata", "-1",
                    "-fflags", "+bitexact", "-flags:a", "+bitexact", str(path)],
                   input=pcm, check=True)  # fmt: skip


def build(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, (make, peak) in SOUNDS.items():
        write(finish(make(), peak), out / f"{name}.mp3")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
