"""Local artifact checks for the runtime verifier; no Podman or inference."""

from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from verify_runtime import verify, verify_png


class RuntimeArtifactTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "synthetic.png"

    def image(self, size=(640, 480), color="white", box=True):
        image = Image.new("RGB", size, color)
        if box:
            ImageDraw.Draw(image).rectangle((100, 100, 300, 300), fill="gray")
        image.save(self.path)

    def test_nonempty_white_background_png_is_accepted(self):
        self.image()
        self.assertEqual(verify_png(self.path), {"width": 640, "height": 480, "white_corners": True, "nonempty": True})

    def test_empty_png_and_colored_background_are_rejected(self):
        for color, box in (("white", False), ("gray", True)):
            with self.subTest(color=color):
                self.image(color=color, box=box)
                with self.assertRaises(ValueError):
                    verify_png(self.path)

    def test_wrong_size_is_rejected(self):
        self.image(size=(320, 240))
        with self.assertRaises(ValueError):
            verify_png(self.path)

    def test_existing_evidence_directory_is_preserved_before_podman(self):
        marker = self.root / "original.txt"
        marker.write_bytes(b"preserve")
        with self.assertRaises(FileExistsError):
            verify("", "not-an-image", self.root, 1)
        self.assertEqual(marker.read_bytes(), b"preserve")


if __name__ == "__main__":
    unittest.main()
