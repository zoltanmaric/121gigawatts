import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('verify', Path(__file__).parents[1] / 'verify.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
BASE = 'http://localhost:2371/'


class Response(io.BytesIO):
    def __init__(self, url, body):
        super().__init__(body)
        self.url = url


class VerifyTests(unittest.TestCase):
    def test_image_sitemap_locations_are_not_html_pages(self):
        documents = {
            BASE + 'sitemap.xml': b'<sitemapindex><sitemap><loc>http://localhost:2371/posts.xml</loc></sitemap></sitemapindex>',
            BASE + 'posts.xml': b'<urlset xmlns:image="http://example.org/image"><url><loc>http://localhost:2371/post/</loc><image:image><image:loc>http://localhost:2371/photo.gif</image:loc></image:image></url></urlset>',
            BASE: b'<html></html>',
            BASE + 'post/': b'<img src="/photo.gif">',
            BASE + 'photo.gif': b'GIF89a\xff',
        }
        def fetch(url, **kwargs):
            return Response(url, documents[url])
        with patch.object(verify, 'urlopen', side_effect=fetch):
            report = verify.verify(BASE)
        self.assertEqual(report['pages'], 2)
        self.assertEqual(report['assets'], 1)
        self.assertEqual(report['failures'], [])

    def test_missing_sitemap_is_failure(self):
        def fetch(url, **kwargs):
            if url.endswith('sitemap.xml'):
                raise OSError('Not found')
            return Response(url, b'<html></html>')
        with patch.object(verify, 'urlopen', side_effect=fetch):
            self.assertEqual(len(verify.verify(BASE)['failures']), 1)

    def test_redirect_to_live_site_is_not_a_successful_preview_check(self):
        with patch.object(verify, 'urlopen', side_effect=lambda *a, **k: Response('https://example.org/', b'')):
            self.assertTrue(verify.verify(BASE)['failures'])
