"""
Model sub-package — ML models, Walk-Forward, Evaluator, Registry.
"""
from model.trainer import ModelTrainer, TrainingConfig
from model.walk_forward import WalkForwardValidator, WalkForwardResult, FoldResult
from model.evaluator import ModelEvaluator, EvaluationResult
from model.xgboost_trainer import XGBoostTrainer, XGBoostConfig
from model.lightgbm_trainer import LightGBMTrainer, LightGBMConfig
from model.ensemble import EnsembleModel, EnsembleConfig
from model.autoencoder import SupervisedAutoencoder, AutoencoderConfig
from model.registry import ModelRegistry, ModelVersion

__all__ = [
    "ModelTrainer",
    "TrainingConfig",
    "WalkForwardValidator",
    "WalkForwardResult",
    "FoldResult",
    "ModelEvaluator",
    "EvaluationResult",
    "XGBoostTrainer",
    "XGBoostConfig",
    "LightGBMTrainer",
    "LightGBMConfig",
    "EnsembleModel",
    "EnsembleConfig",
    "SupervisedAutoencoder",
    "AutoencoderConfig",
    "ModelRegistry",
    "ModelVersion",
]
