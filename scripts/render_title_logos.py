"""Authentic Pixel Typography Compositor for Chrono Trigger DS Russian Title Graphics.
Crafts 100% authentic Square Enix style Cyrillic glyphs matching 3D metallic bevel.
"""

from pathlib import Path
import json
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTRACTED_PNG = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.png"
EXTRACTED_JSON = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.json"
OUTPUT_PNG = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.png"


class GlyphFactory:
    """Builds pixel-perfect Cyrillic glyphs from Square Enix original components."""

    def __init__(self, base_img: Image.Image):
        self.img = base_img
        self.palette = base_img.getpalette()

        # Extract pristine original crops
        # Cell 0: Game Mode (x=8, y=8)
        self.e_orig = self._crop(8 + 85, 8, 8, 24)   # Lowercase 'e' (8x24)
        self.o_orig = self._crop(8 + 66, 8, 9, 24)   # Lowercase 'o' (9x24)
        self.M_orig = self._crop(8 + 49, 8, 17, 24)  # Capital 'M' (17x24)
        self.G_orig = self._crop(8 + 4, 8, 11, 24)   # Capital 'G' (11x24)

        # Cell 1: Battle Mode (x=112, y=8)
        self.B_orig = self._crop(112 + 3, 8, 12, 24) # Capital 'B' (12x24)

        # Cell 2: Movies (x=8, y=56)
        self.i_orig = self._crop(8 + 56, 56, 5, 24)  # Lowercase 'i' (5x24)
        self.v_orig = self._crop(8 + 46, 56, 9, 24)  # Lowercase 'v' (9x24)
        self.s_orig = self._crop(8 + 70, 56, 8, 24)  # Lowercase 's' (8x24)

        # Cell 7: Mode de Combat (x=112, y=136)
        self.b_orig = self._crop(112 + 106, 136, 10, 24) # Lowercase 'b' (10x24)

        # Cell 8: Cinématiques (x=8, y=186)
        self.n_orig = self._crop(8 + 24, 186, 7, 24)     # Lowercase 'n' (7x24)

    def _crop(self, x: int, y: int, w: int, h: int) -> list[list[int]]:
        crop = self.img.crop((x, y, x + w, y + h))
        return [[crop.getpixel((col, row)) for col in range(w)] for row in range(h)]

    def make_P(self) -> list[list[int]]:
        """Capital Russian 'Р' (width 10, height 24).
        Derived from Square Enix Capital 'B': left stem + upper bowl.
        """
        grid = [[0] * 10 for _ in range(24)]
        for y in range(24):
            for x in range(10):
                if y <= 10:
                    p = self.B_orig[y][x + 1] if (x + 1) < len(self.B_orig[y]) else 0
                    grid[y][x] = p
                elif 11 <= y <= 17:
                    if x <= 3:
                        grid[y][x] = self.B_orig[y][x + 1]
                    elif x == 4:
                        grid[y][x] = 2 if y < 17 else 1
                else:
                    if x <= 5:
                        grid[y][x] = self.B_orig[y][x + 1]

        under_shadow = [0, 0, 0, 0, 2, 4, 3, 3, 2, 1]
        for x, c in enumerate(under_shadow):
            if c != 0 and grid[11][x] == 0:
                grid[11][x] = c

        return grid

    def make_B(self) -> list[list[int]]:
        """Capital Russian 'Б' (width 12, height 24).
        Derived from Square Enix Capital 'B': left stem + lower bowl + top Roman bar with serif.
        """
        grid = [[0] * 12 for _ in range(24)]
        for y in range(24):
            for x in range(12):
                if y >= 10:
                    grid[y][x] = self.B_orig[y][x]
                elif y < 10 and x <= 4:
                    grid[y][x] = self.B_orig[y][x]

        top_bar = {
            1: [(4, 0x09), (5, 0x09), (6, 0x0b), (7, 0x0b), (8, 0x0a), (9, 0x04)],
            2: [(4, 0x0b), (5, 0x0c), (6, 0x0d), (7, 0x0e), (8, 0x0e), (9, 0x0e), (10, 0x05)],
            3: [(4, 0x0c), (5, 0x0c), (6, 0x0c), (7, 0x0e), (8, 0x0e), (9, 0x0e), (10, 0x0c), (11, 0x03)],
            4: [(8, 0x05), (9, 0x0e), (10, 0x0c), (11, 0x03)],
            5: [(8, 0x02), (9, 0x0d), (10, 0x0e), (11, 0x05)],
            6: [(8, 0x01), (9, 0x0b), (10, 0x0d), (11, 0x03)],
            7: [(9, 0x04), (10, 0x07), (11, 0x01)],
        }
        for y, row_pixels in top_bar.items():
            for x, col in row_pixels:
                grid[y][x] = col

        return grid

    def make_I_cap(self) -> list[list[int]]:
        """Capital Russian 'И' (width 12, height 24).
        Derived from stems of 'M' connected by glowing metallic diagonal.
        """
        grid = [[0] * 12 for _ in range(24)]
        for y in range(24):
            for x in range(4):
                grid[y][x] = self.M_orig[y][x + 2]
                grid[y][x + 8] = self.M_orig[y][x + 12]

        diag_pixels = {
            4:  [(7, 0x0a), (8, 0x0e)],
            5:  [(6, 0x0b), (7, 0x0e), (8, 0x04)],
            6:  [(6, 0x0d), (7, 0x0e), (8, 0x05)],
            7:  [(5, 0x0b), (6, 0x0e), (7, 0x0e), (8, 0x03)],
            8:  [(5, 0x0d), (6, 0x0e), (7, 0x08), (8, 0x02)],
            9:  [(4, 0x0b), (5, 0x0e), (6, 0x0e), (7, 0x04)],
            10: [(4, 0x0d), (5, 0x0e), (6, 0x08), (7, 0x02)],
            11: [(3, 0x0b), (4, 0x0e), (5, 0x0e), (6, 0x04)],
            12: [(3, 0x0d), (4, 0x0e), (5, 0x08), (6, 0x02)],
            13: [(3, 0x0e), (4, 0x0e), (5, 0x04), (6, 0x01)],
            14: [(2, 0x0a), (3, 0x0e), (4, 0x0a), (5, 0x03)],
            15: [(2, 0x0c), (3, 0x0e), (4, 0x06), (5, 0x02)],
            16: [(2, 0x0d), (3, 0x0c), (4, 0x04), (5, 0x01)],
            17: [(2, 0x0e), (3, 0x08), (4, 0x02)],
            18: [(2, 0x0b), (3, 0x04)],
        }
        for y, row_pixels in diag_pixels.items():
            for x, col in row_pixels:
                if grid[y][x] == 0:
                    grid[y][x] = col

        return grid

    def make_e(self) -> list[list[int]]:
        """Lowercase 'е' (width 8, height 24) directly from SE 'Mode'."""
        return [row[:] for row in self.e_orig]

    def make_o(self) -> list[list[int]]:
        """Lowercase 'о' (width 9, height 24) directly from SE 'Mode'."""
        return [row[:] for row in self.o_orig]

    def make_zh(self) -> list[list[int]]:
        """Lowercase Cyrillic 'ж' (width 9, height 24).
        Central vertical stem (x=3..5, width 3) + curved diagonal branches joining at waist (y=13..14).
        Full-weight 3px stem matching SE standard.
        """
        grid = [[0] * 9 for _ in range(24)]

        # Central vertical stem: x=3..5 at y=7..23
        for y in range(7, 24):
            if y == 7:
                grid[y][2] = 0x04; grid[y][3] = 0x0c; grid[y][4] = 0x0e; grid[y][5] = 0x0a; grid[y][6] = 0x04
            elif y in (8, 9, 10):
                grid[y][3] = 0x0a; grid[y][4] = 0x0e; grid[y][5] = 0x0c
            elif y in (11, 12, 13, 14):
                grid[y][3] = 0x0b; grid[y][4] = 0x0e; grid[y][5] = 0x0e
            elif y in (15, 16, 17):
                grid[y][3] = 0x0b; grid[y][4] = 0x0e; grid[y][5] = 0x0c
            elif y == 18:
                grid[y][3] = 0x07; grid[y][4] = 0x0d; grid[y][5] = 0x0a
            elif y == 19:
                grid[y][3] = 0x04; grid[y][4] = 0x0c; grid[y][5] = 0x08
            elif y == 20:
                grid[y][2] = 0x06; grid[y][3] = 0x0a; grid[y][4] = 0x09; grid[y][5] = 0x07; grid[y][6] = 0x04
            elif y == 21:
                grid[y][2] = 0x04; grid[y][3] = 0x07; grid[y][4] = 0x05; grid[y][5] = 0x04
            elif y == 22:
                grid[y][2] = 0x02; grid[y][3] = 0x04; grid[y][4] = 0x02
            elif y == 23:
                grid[y][3] = 0x02; grid[y][4] = 0x01

        # Left branches
        left_branches = {
            7:  [(0, 0x06), (1, 0x0e), (2, 0x0b)],
            8:  [(0, 0x0a), (1, 0x0e), (2, 0x07)],
            9:  [(1, 0x0c), (2, 0x0e)],
            10: [(1, 0x0a), (2, 0x0e)],
            11: [(1, 0x06), (2, 0x0e)],
            12: [(2, 0x0b), (3, 0x0e)],
            13: [(2, 0x0d), (3, 0x0e)],
            14: [(2, 0x0b), (3, 0x0e)],
            15: [(1, 0x09), (2, 0x0e)],
            16: [(1, 0x0a), (2, 0x0d)],
            17: [(0, 0x06), (1, 0x0e), (2, 0x08)],
            18: [(0, 0x08), (1, 0x0e), (2, 0x07)],
            19: [(0, 0x0a), (1, 0x0e), (2, 0x05)],
            20: [(0, 0x08), (1, 0x0c)],
            21: [(0, 0x05), (1, 0x07)],
            22: [(0, 0x02), (1, 0x03)],
        }
        for y, row_pixels in left_branches.items():
            for x, col in row_pixels:
                grid[y][x] = col

        # Right branches
        right_branches = {
            7:  [(6, 0x0b), (7, 0x0e), (8, 0x06)],
            8:  [(6, 0x08), (7, 0x0e), (8, 0x05)],
            9:  [(6, 0x0e), (7, 0x0b)],
            10: [(6, 0x0e), (7, 0x08)],
            11: [(6, 0x0e), (7, 0x05)],
            12: [(5, 0x0e), (6, 0x0c)],
            13: [(5, 0x0e), (6, 0x0b)],
            14: [(5, 0x0e), (6, 0x09)],
            15: [(6, 0x0e), (7, 0x08)],
            16: [(6, 0x0d), (7, 0x0a)],
            17: [(6, 0x09), (7, 0x0e), (8, 0x04)],
            18: [(6, 0x08), (7, 0x0e), (8, 0x05)],
            19: [(6, 0x06), (7, 0x0e), (8, 0x06)],
            20: [(7, 0x0b), (8, 0x04)],
            21: [(7, 0x07), (8, 0x02)],
            22: [(7, 0x03), (8, 0x01)],
        }
        for y, row_pixels in right_branches.items():
            for x, col in row_pixels:
                grid[y][x] = col

        return grid

    def make_i(self) -> list[list[int]]:
        """Lowercase Cyrillic 'и' (width 8, height 24).
        Two full 3px vertical stems matching SE standard connected by glowing white diagonal.
        """
        grid = [[0] * 8 for _ in range(24)]
        stem_rows = {
            7:  ([0x04, 0x0c, 0x0a], [0x04, 0x0c, 0x0a]),
            8:  ([0x06, 0x0e, 0x0b], [0x06, 0x0e, 0x0b]),
            9:  ([0x0a, 0x0e, 0x0c], [0x0a, 0x0e, 0x0c]),
            10: ([0x0b, 0x0e, 0x0c], [0x0b, 0x0e, 0x0c]),
            11: ([0x0b, 0x0e, 0x0d], [0x0b, 0x0e, 0x0d]),
            12: ([0x0b, 0x0e, 0x0d], [0x0b, 0x0e, 0x0d]),
            13: ([0x0b, 0x0e, 0x0d], [0x0b, 0x0e, 0x0d]),
            14: ([0x0b, 0x0e, 0x0c], [0x0b, 0x0e, 0x0c]),
            15: ([0x0b, 0x0e, 0x0c], [0x0b, 0x0e, 0x0c]),
            16: ([0x0b, 0x0e, 0x0d], [0x0b, 0x0e, 0x0d]),
            17: ([0x0a, 0x0e, 0x0d], [0x0a, 0x0e, 0x0d]),
            18: ([0x07, 0x0d, 0x0c], [0x07, 0x0d, 0x0c]),
            19: ([0x04, 0x0c, 0x0d], [0x04, 0x0c, 0x0d]),
            20: ([0x03, 0x08, 0x0c], [0x03, 0x08, 0x0c]),
            21: ([0x02, 0x04, 0x07], [0x02, 0x04, 0x07]),
            22: ([0x01, 0x02, 0x06], [0x01, 0x02, 0x06]),
            23: ([0x00, 0x01, 0x03], [0x00, 0x01, 0x03]),
        }
        for y, (left, right) in stem_rows.items():
            for x, c in enumerate(left):
                grid[y][x] = c
            for x, c in enumerate(right):
                grid[y][x + 5] = c

        diag = {
            8:  [(4, 0x0b), (5, 0x0e)],
            9:  [(3, 0x0c), (4, 0x0e)],
            10: [(3, 0x0e), (4, 0x0e)],
            11: [(2, 0x0b), (3, 0x0e), (4, 0x07)],
            12: [(2, 0x0d), (3, 0x0e), (4, 0x03)],
            13: [(2, 0x0e), (3, 0x0d)],
            14: [(1, 0x0b), (2, 0x0e), (3, 0x07)],
            15: [(1, 0x0d), (2, 0x0e), (3, 0x03)],
            16: [(1, 0x0e), (2, 0x0b)],
            17: [(1, 0x0e), (2, 0x06)],
        }
        for y, row_pixels in diag.items():
            for x, col in row_pixels:
                grid[y][x] = col

        return grid

    def make_m(self) -> list[list[int]]:
        """Lowercase Cyrillic 'м' (width 9, height 24).
        Two full 3px vertical stems matching SE standard with authentic central metallic V.
        V has wide open top counter and clear diagonal arms meeting at baseline.
        """
        grid = [[0] * 9 for _ in range(24)]
        stem_rows = {
            7:  ([0x04, 0x0c, 0x0a], [0x04, 0x0c, 0x0a]),
            8:  ([0x06, 0x0e, 0x0b], [0x06, 0x0e, 0x0b]),
            9:  ([0x0a, 0x0e, 0x0c], [0x0a, 0x0e, 0x0c]),
            10: ([0x0b, 0x0e, 0x0c], [0x0b, 0x0e, 0x0c]),
            11: ([0x0b, 0x0e, 0x0d], [0x0b, 0x0e, 0x0d]),
            12: ([0x0b, 0x0e, 0x0d], [0x0b, 0x0e, 0x0d]),
            13: ([0x0b, 0x0e, 0x0d], [0x0b, 0x0e, 0x0d]),
            14: ([0x0b, 0x0e, 0x0c], [0x0b, 0x0e, 0x0c]),
            15: ([0x0b, 0x0e, 0x0c], [0x0b, 0x0e, 0x0c]),
            16: ([0x0b, 0x0e, 0x0d], [0x0b, 0x0e, 0x0d]),
            17: ([0x0a, 0x0e, 0x0d], [0x0a, 0x0e, 0x0d]),
            18: ([0x07, 0x0d, 0x0c], [0x07, 0x0d, 0x0c]),
            19: ([0x04, 0x0c, 0x0d], [0x04, 0x0c, 0x0d]),
            20: ([0x03, 0x08, 0x0c], [0x03, 0x08, 0x0c]),
            21: ([0x02, 0x04, 0x07], [0x02, 0x04, 0x07]),
            22: ([0x01, 0x02, 0x06], [0x01, 0x02, 0x06]),
            23: ([0x00, 0x01, 0x03], [0x00, 0x01, 0x03]),
        }
        for y, (left, right) in stem_rows.items():
            for x, c in enumerate(left):
                grid[y][x] = c
            for x, c in enumerate(right):
                grid[y][x + 6] = c

        # Central V: left arm slants from (2, 7) to (4, 17), right arm from (6, 7) to (4, 17)
        # Deep open space at top: cols 3..5 empty at y=7..9!
        v_pixels = {
            7:  [(2, 0x0b), (6, 0x0b)],
            8:  [(2, 0x0e), (6, 0x0e)],
            9:  [(2, 0x0d), (3, 0x0a), (5, 0x0a), (6, 0x0d)],
            10: [(3, 0x0d), (5, 0x0d)],
            11: [(3, 0x0e), (5, 0x0b)],
            12: [(3, 0x0e), (4, 0x0b), (5, 0x08)],
            13: [(3, 0x0c), (4, 0x0e), (5, 0x05)],
            14: [(3, 0x08), (4, 0x0e), (5, 0x02)],
            15: [(3, 0x03), (4, 0x0e)],
            16: [(4, 0x0e)],
            17: [(4, 0x0d)],
            18: [(4, 0x09)],
            19: [(4, 0x04)],
        }
        for y, row_pixels in v_pixels.items():
            for x, col in row_pixels:
                grid[y][x] = col

        return grid

    def make_g(self) -> list[list[int]]:
        """Lowercase Cyrillic 'г' (width 7, height 24).
        Vertical stem with bottom serif + top bar with downward hook terminal.
        """
        grid = [[0] * 7 for _ in range(24)]
        for y in range(7, 24):
            if y == 7:
                grid[y][0] = 0x06; grid[y][1] = 0x0e; grid[y][2] = 0x0b
            elif y in (8, 9, 10):
                grid[y][0] = 0x0a; grid[y][1] = 0x0e; grid[y][2] = 0x0c
            elif y in (11, 12, 13):
                grid[y][0] = 0x0b; grid[y][1] = 0x0e; grid[y][2] = 0x0d
            elif y in (14, 15, 16):
                grid[y][0] = 0x0b; grid[y][1] = 0x0e; grid[y][2] = 0x0c
            elif y in (17, 18):
                grid[y][0] = 0x0a; grid[y][1] = 0x0e; grid[y][2] = 0x0c
            elif y == 19:
                grid[y][0] = 0x08; grid[y][1] = 0x0d; grid[y][2] = 0x0a
            elif y == 20:
                grid[y][0] = 0x07; grid[y][1] = 0x0a; grid[y][2] = 0x08
            elif y == 21:
                grid[y][0] = 0x06; grid[y][1] = 0x07; grid[y][2] = 0x05
            elif y == 22:
                grid[y][0] = 0x04; grid[y][1] = 0x05; grid[y][2] = 0x02
            elif y == 23:
                grid[y][1] = 0x02; grid[y][2] = 0x01

        top_hook = {
            7:  [(2, 0x0d), (3, 0x0e), (4, 0x0e), (5, 0x0e), (6, 0x06)],
            8:  [(2, 0x0e), (3, 0x0e), (4, 0x0e), (5, 0x0e), (6, 0x09)],
            9:  [(4, 0x06), (5, 0x0e), (6, 0x09)],
            10: [(5, 0x0b), (6, 0x07)],
            11: [(5, 0x06), (6, 0x02)],
        }
        for y, row_pixels in top_hook.items():
            for x, col in row_pixels:
                grid[y][x] = col

        return grid

    def make_r(self) -> list[list[int]]:
        """Lowercase Cyrillic 'р' (width 8, height 24).
        Stem descending to y=22 + bowl from SE 'b' attached to right.
        """
        grid = [[0] * 8 for _ in range(24)]
        for y in range(7, 23):
            if y == 7:
                grid[y][0] = 0x06; grid[y][1] = 0x0e; grid[y][2] = 0x0b
            elif y in (8, 9, 10):
                grid[y][0] = 0x0a; grid[y][1] = 0x0e; grid[y][2] = 0x0c
            elif y in (11, 12, 13):
                grid[y][0] = 0x0b; grid[y][1] = 0x0e; grid[y][2] = 0x0d
            elif y in (14, 15, 16):
                grid[y][0] = 0x0b; grid[y][1] = 0x0e; grid[y][2] = 0x0c
            elif y in (17, 18, 19):
                grid[y][0] = 0x0a; grid[y][1] = 0x0e; grid[y][2] = 0x0a
            elif y == 20:
                grid[y][0] = 0x06; grid[y][1] = 0x0b; grid[y][2] = 0x06
            elif y == 21:
                grid[y][0] = 0x04; grid[y][1] = 0x07; grid[y][2] = 0x04
            elif y == 22:
                grid[y][0] = 0x02; grid[y][1] = 0x03; grid[y][2] = 0x01

        for y in range(7, 19):
            for x in range(6):
                c = self.b_orig[y][x + 4]
                if c != 0:
                    grid[y][x + 2] = c

        return grid

    def make_y(self) -> list[list[int]]:
        """Lowercase Cyrillic 'ы' (width 12, height 24).
        Soft sign 'ь' (from SE 'b') + 1px gap + vertical stem 'ı' (from SE 'i').
        """
        grid = [[0] * 12 for _ in range(24)]
        for y in range(7, 24):
            for x in range(8):
                grid[y][x] = self.b_orig[y][x + 2]
        for y in range(7, 24):
            for x in range(3):
                grid[y][x + 9] = self.i_orig[y][x + 1]

        return grid

    def make_ya(self) -> list[list[int]]:
        """Lowercase Cyrillic 'я' (width 9, height 24).
        Vertical right stem + top-left bowl + slanting lower-left leg with serif foot.
        """
        grid = [[0] * 9 for _ in range(24)]
        for y in range(7, 24):
            if y == 7:
                grid[y][6] = 0x06; grid[y][7] = 0x0e; grid[y][8] = 0x0b
            elif y in (8, 9, 10):
                grid[y][6] = 0x0a; grid[y][7] = 0x0e; grid[y][8] = 0x0c
            elif y in (11, 12, 13):
                grid[y][6] = 0x0b; grid[y][7] = 0x0e; grid[y][8] = 0x0d
            elif y in (14, 15, 16):
                grid[y][6] = 0x0b; grid[y][7] = 0x0e; grid[y][8] = 0x0c
            elif y in (17, 18):
                grid[y][6] = 0x0a; grid[y][7] = 0x0e; grid[y][8] = 0x0c
            elif y == 19:
                grid[y][6] = 0x08; grid[y][7] = 0x0d; grid[y][8] = 0x0a
            elif y == 20:
                grid[y][6] = 0x07; grid[y][7] = 0x0a; grid[y][8] = 0x08
            elif y == 21:
                grid[y][6] = 0x06; grid[y][7] = 0x07; grid[y][8] = 0x05
            elif y == 22:
                grid[y][6] = 0x04; grid[y][7] = 0x05; grid[y][8] = 0x02
            elif y == 23:
                grid[y][7] = 0x02; grid[y][8] = 0x01

        bowl = {
            7:  [(2, 0x06), (3, 0x0b), (4, 0x0d), (5, 0x0e), (6, 0x0b)],
            8:  [(1, 0x08), (2, 0x0e), (3, 0x0e), (4, 0x0e), (5, 0x0e), (6, 0x09)],
            9:  [(1, 0x0b), (2, 0x0e), (3, 0x08), (4, 0x06), (5, 0x0d), (6, 0x09)],
            10: [(1, 0x0b), (2, 0x0e), (3, 0x04), (4, 0x03), (5, 0x0d), (6, 0x09)],
            11: [(1, 0x09), (2, 0x0e), (3, 0x07), (4, 0x07), (5, 0x0e), (6, 0x09)],
            12: [(1, 0x06), (2, 0x0e), (3, 0x0e), (4, 0x0e), (5, 0x0e), (6, 0x08)],
            13: [(2, 0x07), (3, 0x0b), (4, 0x0d), (5, 0x0d), (6, 0x08)],
        }
        for y, row_pixels in bowl.items():
            for x, col in row_pixels:
                grid[y][x] = col

        leg = {
            14: [(4, 0x0a), (5, 0x0e), (6, 0x08)],
            15: [(3, 0x0a), (4, 0x0e), (5, 0x0a)],
            16: [(3, 0x0c), (4, 0x0e), (5, 0x07)],
            17: [(2, 0x0b), (3, 0x0e), (4, 0x08)],
            18: [(2, 0x0d), (3, 0x0e), (4, 0x05)],
            19: [(1, 0x0a), (2, 0x0e), (3, 0x08)],
            20: [(1, 0x0c), (2, 0x0e), (3, 0x05)],
            21: [(0, 0x08), (1, 0x0c), (2, 0x08), (3, 0x03)],
            22: [(0, 0x05), (1, 0x08), (2, 0x05)],
            23: [(0, 0x02), (1, 0x03)],
        }
        for y, row_pixels in leg.items():
            for x, col in row_pixels:
                grid[y][x] = col

        return grid

    def make_l(self) -> list[list[int]]:
        """Lowercase Cyrillic 'л' (width 8, height 24).
        Slanted left leg with bottom hook + vertical right stem + rounded arch.
        """
        grid = [[0] * 8 for _ in range(24)]
        for y in range(7, 24):
            if y == 7:
                grid[y][5] = 0x06; grid[y][6] = 0x0e; grid[y][7] = 0x0b
            elif y in (8, 9, 10):
                grid[y][5] = 0x0a; grid[y][7] = 0x0c; grid[y][6] = 0x0e
            elif y in (11, 12, 13):
                grid[y][5] = 0x0b; grid[y][6] = 0x0e; grid[y][7] = 0x0d
            elif y in (14, 15, 16):
                grid[y][5] = 0x0b; grid[y][6] = 0x0e; grid[y][7] = 0x0c
            elif y in (17, 18):
                grid[y][5] = 0x0a; grid[y][6] = 0x0e; grid[y][7] = 0x0c
            elif y == 19:
                grid[y][5] = 0x08; grid[y][6] = 0x0d; grid[y][7] = 0x0a
            elif y == 20:
                grid[y][5] = 0x07; grid[y][6] = 0x0a; grid[y][7] = 0x08
            elif y == 21:
                grid[y][5] = 0x06; grid[y][6] = 0x07; grid[y][7] = 0x05
            elif y == 22:
                grid[y][5] = 0x04; grid[y][6] = 0x05; grid[y][7] = 0x02
            elif y == 23:
                grid[y][6] = 0x02; grid[y][7] = 0x01

        left_leg = {
            7:  [(2, 0x06), (3, 0x0b), (4, 0x0e), (5, 0x0d)],
            8:  [(2, 0x09), (3, 0x0e), (4, 0x0e), (5, 0x0b)],
            9:  [(2, 0x0b), (3, 0x0e), (4, 0x0a)],
            10: [(2, 0x0c), (3, 0x0e), (4, 0x07)],
            11: [(1, 0x09), (2, 0x0e), (3, 0x0c)],
            12: [(1, 0x0a), (2, 0x0e), (3, 0x09)],
            13: [(1, 0x0b), (2, 0x0e), (3, 0x07)],
            14: [(1, 0x0b), (2, 0x0e), (3, 0x05)],
            15: [(1, 0x0c), (2, 0x0e), (3, 0x04)],
            16: [(0, 0x08), (1, 0x0d), (2, 0x0e)],
            17: [(0, 0x0a), (1, 0x0e), (2, 0x0b)],
            18: [(0, 0x0c), (1, 0x0e), (2, 0x08)],
            19: [(0, 0x0c), (1, 0x0e), (2, 0x05)],
            20: [(0, 0x0a), (1, 0x0b), (2, 0x04)],
            21: [(0, 0x06), (1, 0x08), (2, 0x02)],
            22: [(0, 0x04), (1, 0x05)],
        }
        for y, row_pixels in left_leg.items():
            for x, col in row_pixels:
                grid[y][x] = col

        return grid

    def make_k(self) -> list[list[int]]:
        """Lowercase Cyrillic 'к' (width 8, height 24).
        Vertical left stem + diagonal upper arm with serif + diagonal lower leg with foot serif.
        """
        grid = [[0] * 8 for _ in range(24)]
        for y in range(7, 24):
            if y == 7:
                grid[y][0] = 0x06; grid[y][1] = 0x0e; grid[y][2] = 0x0b
            elif y in (8, 9, 10):
                grid[y][0] = 0x0a; grid[y][1] = 0x0e; grid[y][2] = 0x0c
            elif y in (11, 12, 13):
                grid[y][0] = 0x0b; grid[y][1] = 0x0e; grid[y][2] = 0x0d
            elif y in (14, 15, 16):
                grid[y][0] = 0x0b; grid[y][1] = 0x0e; grid[y][2] = 0x0c
            elif y in (17, 18):
                grid[y][0] = 0x0a; grid[y][1] = 0x0e; grid[y][2] = 0x0c
            elif y == 19:
                grid[y][0] = 0x08; grid[y][1] = 0x0d; grid[y][2] = 0x0a
            elif y == 20:
                grid[y][0] = 0x07; grid[y][1] = 0x0a; grid[y][2] = 0x08
            elif y == 21:
                grid[y][0] = 0x06; grid[y][1] = 0x07; grid[y][2] = 0x05
            elif y == 22:
                grid[y][0] = 0x04; grid[y][1] = 0x05; grid[y][2] = 0x02
            elif y == 23:
                grid[y][1] = 0x02; grid[y][2] = 0x01

        upper_arm = {
            7:  [(5, 0x06), (6, 0x0e), (7, 0x09)],
            8:  [(5, 0x09), (6, 0x0e), (7, 0x06)],
            9:  [(4, 0x0a), (5, 0x0e), (6, 0x08)],
            10: [(4, 0x0d), (5, 0x0e), (6, 0x05)],
            11: [(3, 0x0a), (4, 0x0e), (5, 0x07)],
            12: [(3, 0x0c), (4, 0x0e), (5, 0x05)],
            13: [(2, 0x09), (3, 0x0e), (4, 0x07)],
        }
        for y, row_pixels in upper_arm.items():
            for x, col in row_pixels:
                grid[y][x] = col

        lower_leg = {
            14: [(3, 0x0c), (4, 0x0a)],
            15: [(3, 0x0e), (4, 0x0b)],
            16: [(3, 0x09), (4, 0x0e), (5, 0x07)],
            17: [(4, 0x0c), (5, 0x0e), (6, 0x06)],
            18: [(4, 0x0a), (5, 0x0e), (6, 0x09)],
            19: [(5, 0x0b), (6, 0x0e), (7, 0x06)],
            20: [(5, 0x09), (6, 0x0d), (7, 0x07)],
            21: [(5, 0x05), (6, 0x0a), (7, 0x05)],
            22: [(6, 0x05), (7, 0x02)],
        }
        for y, row_pixels in lower_leg.items():
            for x, col in row_pixels:
                grid[y][x] = col

        return grid


def blit_glyph(canvas: list[list[int]], glyph: list[list[int]], dst_x: int, dst_y: int = 0):
    """Blits a glyph onto canvas preserving non-zero pixels."""
    h = len(glyph)
    w = len(glyph[0])
    for y in range(h):
        for x in range(w):
            val = glyph[y][x]
            if val != 0:
                canvas[dst_y + y][dst_x + x] = val


def render_subtitle(canvas: list[list[int]], dst_x: int, dst_y: int):
    """Renders the crisp white subtitle 'Бой в реальном времени вер. 2' with drop shadow.
    Fits comfortably inside 64px width (x=16..80), centered at local offset 6..58.
    """
    font = {
        'Б': ["111", "100", "110", "101", "110"],
        'о': ["010", "101", "101", "101", "010"],
        'й': ["101", "101", "111", "101", "101"],
        'в': ["110", "101", "110", "101", "110"],
        'р': ["110", "101", "110", "100", "100"],
        'е': ["111", "100", "110", "100", "111"],
        'а': ["010", "101", "111", "101", "101"],
        'л': ["011", "001", "001", "101", "101"],
        'ь': ["100", "100", "110", "101", "110"],
        'н': ["101", "101", "111", "101", "101"],
        'м': ["1001", "1111", "1001", "1001", "1001"],
        'и': ["101", "101", "111", "101", "101"],
        '.': ["0", "0", "0", "0", "1"],
        '2': ["110", "001", "010", "100", "111"],
        ' ': ["0"],
    }

    def draw_text(text: str, start_x: int, start_y: int):
        cur_x = start_x
        for ch in text:
            bmp = font.get(ch)
            if not bmp:
                cur_x += 2
                continue
            char_w = len(bmp[0])
            for row_idx, row_str in enumerate(bmp):
                for col_idx, bit in enumerate(row_str):
                    if bit == '1':
                        canvas[start_y + row_idx + 1][cur_x + col_idx + 1] = 1
            for row_idx, row_str in enumerate(bmp):
                for col_idx, bit in enumerate(row_str):
                    if bit == '1':
                        canvas[start_y + row_idx][cur_x + col_idx] = 15
            cur_x += char_w + 1

    draw_text("Бой в реальном", dst_x + 6, dst_y + 2)
    draw_text("времени вер. 2", dst_x + 7, dst_y + 9)


def generate_title_logo_sheet() -> Image.Image:
    """Generates the full 256x250 translated title logo sheet."""
    orig = Image.open(EXTRACTED_PNG)
    palette = orig.getpalette()

    factory = GlyphFactory(orig)

    canvas = [[orig.getpixel((x, y)) for x in range(256)] for y in range(250)]

    P = factory.make_P()
    B = factory.make_B()
    I_cap = factory.make_I_cap()
    e = factory.make_e()
    o = factory.make_o()
    m = factory.make_m()
    i = factory.make_i()
    zh = factory.make_zh()
    g = factory.make_g()
    r = factory.make_r()
    y_ch = factory.make_y()
    ya = factory.make_ya()
    l = factory.make_l()
    k = factory.make_k()

    # Clear Cell 0, 1, 2, 3, 4, 5 areas
    cells_to_clear = [
        (8, 8, 96, 24),     # Cell 0
        (112, 8, 96, 40),   # Cell 1
        (8, 56, 96, 24),    # Cell 2
        (112, 56, 100, 24), # Cell 3
        (8, 88, 100, 40),   # Cell 4
        (116, 88, 96, 24),  # Cell 5
    ]
    for cx, cy, w, h in cells_to_clear:
        for y in range(h):
            for x in range(w):
                canvas[cy + y][cx + x] = 0

    # -------------------------------------------------------------
    # Render Cell 0: 'Режим Игры' (96x24 at x=8, y=8)
    # Left OAM: 'Режим' (width 47: x=1..47, x=48 empty)
    # Right OAM: 'Игры' (width 41: x=50..91)
    # -------------------------------------------------------------
    c0_x, c0_y = 8, 8
    # 'Режим':
    blit_glyph(canvas, P, c0_x + 1, c0_y)    # P: x=1..10 (width 10)
    blit_glyph(canvas, e, c0_x + 11, c0_y)   # e: x=11..18 (width 8, x=19 empty)
    blit_glyph(canvas, zh, c0_x + 20, c0_y)  # ж: x=20..28 (width 9, x=29 empty)
    blit_glyph(canvas, i, c0_x + 30, c0_y)   # и: x=30..37 (width 8, x=38 empty)
    blit_glyph(canvas, m, c0_x + 39, c0_y)   # м: x=39..47 (width 9)

    # 'Игры':
    blit_glyph(canvas, I_cap, c0_x + 50, c0_y) # И: x=50..61 (width 12)
    blit_glyph(canvas, g, c0_x + 63, c0_y)     # г: x=63..69 (width 7)
    blit_glyph(canvas, r, c0_x + 71, c0_y)     # р: x=71..78 (width 8)
    blit_glyph(canvas, y_ch, c0_x + 80, c0_y)  # ы: x=80..91 (width 12)

    # -------------------------------------------------------------
    # Render Cell 1: 'Режим Боя' (96x40 at x=112, y=8)
    # Left OAM: 'Режим' (identical to Cell 0)
    # Right OAM: 'Боя' (width 32: x=55..86)
    # Subtitle: inside x=16..80
    # -------------------------------------------------------------
    c1_x, c1_y = 112, 8
    # 'Режим':
    blit_glyph(canvas, P, c1_x + 1, c1_y)
    blit_glyph(canvas, e, c1_x + 11, c1_y)
    blit_glyph(canvas, zh, c1_x + 20, c1_y)
    blit_glyph(canvas, i, c1_x + 30, c1_y)
    blit_glyph(canvas, m, c1_x + 39, c1_y)

    # 'Боя':
    blit_glyph(canvas, B, c1_x + 55, c1_y)   # Б: x=55..66 (width 12)
    blit_glyph(canvas, o, c1_x + 68, c1_y)   # о: x=68..76 (width 9)
    blit_glyph(canvas, ya, c1_x + 78, c1_y)  # я: x=78..86 (width 9)

    # Subtitle: inside x=16..80
    render_subtitle(canvas, c1_x + 16, c1_y + 24)

    # -------------------------------------------------------------
    # Render Cell 2: 'Ролики' (96x24 at x=8, y=56)
    # Centered: width 56, starts at x=20, ends at x=75
    # -------------------------------------------------------------
    c2_x, c2_y = 8, 56
    blit_glyph(canvas, P, c2_x + 20, c2_y)   # Р: x=20..29 (width 10)
    blit_glyph(canvas, o, c2_x + 31, c2_y)   # о: x=31..39 (width 9)
    blit_glyph(canvas, l, c2_x + 41, c2_y)   # л: x=41..48 (width 8)
    blit_glyph(canvas, i, c2_x + 50, c2_y)   # и: x=50..57 (width 8)
    blit_glyph(canvas, k, c2_x + 59, c2_y)   # к: x=59..66 (width 8)
    blit_glyph(canvas, i, c2_x + 68, c2_y)   # и: x=68..75 (width 8)

    # -------------------------------------------------------------
    # Replicate to Cell 3, 4, 5 with hardware OAM offsets
    # -------------------------------------------------------------
    # Cell 3 (100x24 at x=112, y=56):
    c3_x, c3_y = 112, 56
    for y in range(24):
        for x in range(48):
            canvas[c3_y + y][c3_x + x] = canvas[c0_y + y][c0_x + x]
        for x in range(48):
            canvas[c3_y + y][c3_x + 52 + x] = canvas[c0_y + y][c0_x + 48 + x]

    # Cell 4 (100x40 at x=8, y=88):
    c4_x, c4_y = 8, 88
    for y in range(24):
        for x in range(48):
            canvas[c4_y + y][c4_x + x] = canvas[c1_y + y][c1_x + x]
        for x in range(48):
            canvas[c4_y + y][c4_x + 52 + x] = canvas[c1_y + y][c1_x + 48 + x]
    for y in range(24, 40):
        for x in range(64):
            canvas[c4_y + y][c4_x + 18 + x] = canvas[c1_y + y][c1_x + 16 + x]

    # Cell 5 (96x24 at x=116, y=88):
    c5_x, c5_y = 116, 88
    for y in range(24):
        for x in range(96):
            canvas[c5_y + y][c5_x + x] = canvas[c2_y + y][c2_x + x]

    res = Image.new("P", (256, 250), 0)
    res.putpalette(palette)
    for y in range(250):
        for x in range(256):
            res.putpixel((x, y), canvas[y][x])

    return res


def main():
    print("Generating authentic Cyrillic title logo sheet...")
    img = generate_title_logo_sheet()
    OUTPUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT_PNG)
    print(f"Successfully saved authentic Russian title logo to {OUTPUT_PNG}")


if __name__ == "__main__":
    main()
