"""
Tests for ScannerService live model integration & auto inference.
"""
import pandas as pd
import pytest
import os
from unittest.mock import MagicMock

from app.services.scanner_service import ScannerService


class TestScannerServiceLiveModel:
    def test_scanner_service_init_and_scan(self):
        service = ScannerService()
        assert service is not None

    def test_scan_combined_fallback_without_model(self):
        service = ScannerService()
        service._loaded_model = None
        results = service.scan_combined()
        assert isinstance(results, list)

    def test_scan_combined_with_auto_inference_mock(self):
        service = ScannerService()
        mock_model = MagicMock()
        import numpy as np
        mock_model.predict_proba.return_value = np.array([[0.1, 0.2, 0.7]])
        service._loaded_model = mock_model

        results = service.scan_combined()
        assert isinstance(results, list)
