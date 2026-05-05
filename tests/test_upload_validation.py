from app.routes.products import allowed_file, validate_image_bytes, safe_content_type


class TestAllowedFile:
    def test_png(self):
        assert allowed_file('photo.png') is True

    def test_jpg(self):
        assert allowed_file('photo.jpg') is True

    def test_jpeg(self):
        assert allowed_file('photo.jpeg') is True

    def test_gif(self):
        assert allowed_file('photo.gif') is True

    def test_webp(self):
        assert allowed_file('photo.webp') is True

    def test_no_extension(self):
        assert allowed_file('photo') is False

    def test_wrong_extension(self):
        assert allowed_file('photo.pdf') is False

    def test_svg_rejected(self):
        assert allowed_file('photo.svg') is False

    def test_exe_rejected(self):
        assert allowed_file('malware.exe') is False


class TestValidateImageBytes:
    def test_valid_jpeg(self):
        assert validate_image_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100, 'jpg') is True

    def test_valid_png(self):
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        assert validate_image_bytes(png_header, 'png') is True

    def test_invalid_jpeg(self):
        assert validate_image_bytes(b'GIF89a' + b'\x00' * 100, 'jpg') is False

    def test_invalid_png(self):
        assert validate_image_bytes(b'\xff\xd8\xff' + b'\x00' * 100, 'png') is False

    def test_valid_gif87a(self):
        assert validate_image_bytes(b'GIF87a' + b'\x00' * 100, 'gif') is True

    def test_valid_gif89a(self):
        assert validate_image_bytes(b'GIF89a' + b'\x00' * 100, 'gif') is True

    def test_valid_webp(self):
        webp = b'RIFF' + b'\x00' * 4 + b'WEBP' + b'\x00' * 100
        assert validate_image_bytes(webp, 'webp') is True

    def test_empty_bytes(self):
        assert validate_image_bytes(b'', 'jpg') is False


class TestSafeContentType:
    def test_jpg(self):
        assert safe_content_type('jpg') == 'image/jpeg'

    def test_jpeg(self):
        assert safe_content_type('jpeg') == 'image/jpeg'

    def test_png(self):
        assert safe_content_type('png') == 'image/png'

    def test_gif(self):
        assert safe_content_type('gif') == 'image/gif'

    def test_webp(self):
        assert safe_content_type('webp') == 'image/webp'

    def test_unknown(self):
        assert safe_content_type('exe') == 'application/octet-stream'

    def test_case_insensitive(self):
        assert safe_content_type('JPG') == 'image/jpeg'
