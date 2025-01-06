"""
This test file tests evelib.sde.EVESDE specific behavior, such as loading and caching.

Requires the SDE to be downloaded to run properly.
"""

import asyncio
from datetime import datetime

import pytest
from aioresponses import aioresponses, CallbackResult
from evelib.sde import EVESDE, SDE_CHECKSUM_DOWNLOAD_URL

from . import utils


@pytest.fixture(name="clean_sde")
async def fixture_clean_sde() -> EVESDE:
    sde = EVESDE()
    yield sde
    await sde.close_session()


# TODO: Add stateful_sde


class TestSDECaching:
    def test_clear_caches(self, clean_sde, tmp_path, monkeypatch):
        import evelib.constants
        monkeypatch.setattr(evelib.constants, "FILE_CACHE_DIR", str(tmp_path))

        universe_file = tmp_path / evelib.constants.SPACE_CACHE_FILENAME
        universe_file.touch()  # Create universe cache file.
        assert universe_file.exists()  # Make sure touch actually worked.

        clean_sde.clear_caches()
        assert not universe_file.exists()

        clean_sde.clear_caches()  # It shouldn't error if no cache exists.

    async def test_checksum(self, clean_sde, tmp_path, monkeypatch):
        import evelib.constants
        monkeypatch.setattr(evelib.constants, "FILE_CACHE_DIR", str(tmp_path))

        checksum_string = "testchecksumpleaseignore"

        checksum_path = tmp_path / evelib.constants.SDE_CHECKSUM_FILENAME
        assert not checksum_path.exists()

        with aioresponses() as m:
            m.get(SDE_CHECKSUM_DOWNLOAD_URL, body=checksum_string, repeat=True)

            assert not (await clean_sde._sde_checksum_match())  # Should fail, checksum file does not exist.
            m.assert_called_once()
            m.requests.clear()

            assert checksum_path.exists()  # It should have written the checksum file to disk.
            with open(checksum_path, "r") as f:
                overwritten_checksum = f.read()

            assert overwritten_checksum == checksum_string

            assert await clean_sde._sde_checksum_match()  # Should work, checksum file exists and matches.
            m.assert_called_once()
            m.requests.clear()

            with open(checksum_path, "w") as f:
                f.write(checksum_string + "error")

            assert not (await clean_sde._sde_checksum_match())  # Should fail, checksum file on disk does not match.
            m.assert_called_once()
            m.requests.clear()

            assert checksum_path.exists()  # It should have written the correct checksum in its place.
            with open(checksum_path, "r") as f:
                overwritten_checksum = f.read()

            assert overwritten_checksum == checksum_string


















