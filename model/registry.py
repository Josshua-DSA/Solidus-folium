"""
Model Registry — Centralized model versioning, tracking, and management.

Menyediakan:
  - Registrasi otomatis model artifacts setelah training.
  - Tracking metrik OOS (Accuracy, F1, AUC, Log-Loss) per versi model.
  - Promote/demote model (staging → production → archived).
  - Load model berdasarkan versi atau status (latest, production).
  - SQLite-backed registry untuk persistence lintas sesi.

Layer: model/ — ML Models & Infrastructure.
"""
import os
import json
import sqlite3
import pickle
import logging
import shutil
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Model lifecycle stages
STAGE_STAGING = "staging"
STAGE_PRODUCTION = "production"
STAGE_ARCHIVED = "archived"


@dataclass
class ModelVersion:
    """Metadata untuk satu versi model yang terdaftar."""
    version_id: str           # e.g. "xgboost_v001"
    model_type: str           # e.g. "xgboost", "lightgbm", "ensemble"
    artifact_path: str        # path ke file .pkl
    stage: str = STAGE_STAGING
    created_at: str = ""
    description: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class ModelRegistry:
    """
    Registry terpusat untuk mengelola versi model ML.

    Menyimpan metadata model di SQLite (`artifacts/registry.db`)
    dan artefak .pkl di `artifacts/saved_models/`.

    Args:
        artifacts_dir: Direktori penyimpanan artefak model.
        db_path: Path ke database registry SQLite.
    """

    def __init__(
        self,
        artifacts_dir: str = "artifacts/saved_models",
        db_path: str = "artifacts/registry.db",
    ):
        self.artifacts_dir = Path(artifacts_dir)
        self.db_path = db_path
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """Buat tabel registry jika belum ada."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_versions (
                    version_id TEXT PRIMARY KEY,
                    model_type TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    stage TEXT NOT NULL DEFAULT 'staging',
                    created_at TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    metrics_json TEXT DEFAULT '{}',
                    config_json TEXT DEFAULT '{}',
                    tags_json TEXT DEFAULT '[]'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_stage
                ON model_versions(model_type, stage)
            """)

    # =========================================================================
    # Registration
    # =========================================================================

    def register(
        self,
        model_type: str,
        artifact_path: str,
        metrics: Dict[str, float],
        config: Optional[Dict[str, Any]] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
        stage: str = STAGE_STAGING,
    ) -> ModelVersion:
        """
        Registrasi model baru ke registry.

        Args:
            model_type: Tipe model (xgboost, lightgbm, ensemble, autoencoder).
            artifact_path: Path ke file .pkl model.
            metrics: Dict metrik OOS (accuracy, f1_macro, auc_ovr, log_loss, dll).
            config: Hyperparameter konfigurasi yang digunakan.
            description: Deskripsi singkat tentang model ini.
            tags: Tag/label opsional.
            stage: Stage awal model (default: staging).

        Returns:
            ModelVersion yang terdaftar.
        """
        # Auto-generate version_id
        existing = self.list_versions(model_type=model_type)
        next_num = len(existing) + 1
        version_id = f"{model_type}_v{next_num:03d}"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        mv = ModelVersion(
            version_id=version_id,
            model_type=model_type,
            artifact_path=str(artifact_path),
            stage=stage,
            created_at=created_at,
            description=description,
            metrics=metrics or {},
            config=config or {},
            tags=tags or [],
        )

        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO model_versions
                (version_id, model_type, artifact_path, stage, created_at,
                 description, metrics_json, config_json, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mv.version_id, mv.model_type, mv.artifact_path, mv.stage,
                mv.created_at, mv.description,
                json.dumps(mv.metrics), json.dumps(mv.config), json.dumps(mv.tags),
            ))

        logger.info("Registered model %s (stage=%s, accuracy=%.4f)",
                     version_id, stage, metrics.get("accuracy", 0))
        return mv

    # =========================================================================
    # Querying
    # =========================================================================

    def list_versions(
        self,
        model_type: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> List[ModelVersion]:
        """List semua versi model dengan filter opsional."""
        query = "SELECT * FROM model_versions WHERE 1=1"
        params: list = []

        if model_type:
            query += " AND model_type = ?"
            params.append(model_type)
        if stage:
            query += " AND stage = ?"
            params.append(stage)

        query += " ORDER BY created_at DESC, rowid DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_version(r) for r in rows]

    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """Ambil ModelVersion berdasarkan version_id."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM model_versions WHERE version_id = ?",
                (version_id,)
            ).fetchone()
        return self._row_to_version(row) if row else None

    def get_production_model(self, model_type: str = "xgboost") -> Optional[ModelVersion]:
        """Ambil model yang sedang berstatus 'production'."""
        versions = self.list_versions(model_type=model_type, stage=STAGE_PRODUCTION)
        return versions[0] if versions else None

    def get_latest(self, model_type: Optional[str] = None) -> Optional[ModelVersion]:
        """Ambil model terakhir yang didaftarkan (apapun stage-nya)."""
        versions = self.list_versions(model_type=model_type)
        return versions[0] if versions else None

    # =========================================================================
    # Lifecycle Management (Promote / Demote / Archive)
    # =========================================================================

    def promote(self, version_id: str, to_stage: str = STAGE_PRODUCTION) -> ModelVersion:
        """
        Promote model ke stage tertentu.
        Jika promote ke 'production', demote model production yang lama ke 'archived'.
        """
        mv = self.get_version(version_id)
        if mv is None:
            raise ValueError(f"Model version '{version_id}' not found in registry.")

        # Demote current production model(s) for this type
        if to_stage == STAGE_PRODUCTION:
            current_prod = self.list_versions(model_type=mv.model_type, stage=STAGE_PRODUCTION)
            for old in current_prod:
                self._update_stage(old.version_id, STAGE_ARCHIVED)
                logger.info("Demoted %s from production to archived", old.version_id)

        self._update_stage(version_id, to_stage)
        mv.stage = to_stage
        logger.info("Promoted %s to %s", version_id, to_stage)
        return mv

    def archive(self, version_id: str) -> None:
        """Archive model (soft-delete)."""
        self._update_stage(version_id, STAGE_ARCHIVED)
        logger.info("Archived model %s", version_id)

    def delete(self, version_id: str, delete_artifact: bool = False) -> None:
        """Hapus model dari registry (dan opsional hapus file .pkl)."""
        mv = self.get_version(version_id)
        if mv is None:
            return

        if delete_artifact and os.path.exists(mv.artifact_path):
            os.remove(mv.artifact_path)
            logger.info("Deleted artifact file: %s", mv.artifact_path)

        with self._connect() as conn:
            conn.execute("DELETE FROM model_versions WHERE version_id = ?", (version_id,))
        logger.info("Deleted model %s from registry", version_id)

    # =========================================================================
    # Model Loading
    # =========================================================================

    def load_model(self, version_id: Optional[str] = None, model_type: str = "xgboost"):
        """
        Load model object dari artifact.

        Jika version_id diberikan, load versi spesifik.
        Jika tidak, cari model production → latest staging → latest apapun.
        """
        if version_id:
            mv = self.get_version(version_id)
        else:
            mv = self.get_production_model(model_type)
            if mv is None:
                mv = self.get_latest(model_type)

        if mv is None:
            logger.warning("No model found in registry for type=%s", model_type)
            return None

        if not os.path.exists(mv.artifact_path):
            logger.error("Artifact file not found: %s", mv.artifact_path)
            return None

        with open(mv.artifact_path, "rb") as f:
            data = pickle.load(f)

        logger.info("Loaded model %s (stage=%s) from %s", mv.version_id, mv.stage, mv.artifact_path)
        return data

    # =========================================================================
    # Comparison & Analytics
    # =========================================================================

    def compare(self, model_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Bandingkan semua versi model berdasarkan metrik OOS.

        Returns:
            List of dicts sorted by f1_macro descending.
        """
        versions = self.list_versions(model_type=model_type)
        rows = []
        for mv in versions:
            rows.append({
                "version_id": mv.version_id,
                "model_type": mv.model_type,
                "stage": mv.stage,
                "created_at": mv.created_at,
                "accuracy": mv.metrics.get("accuracy", 0),
                "f1_macro": mv.metrics.get("f1_macro", 0),
                "auc_ovr": mv.metrics.get("auc_ovr", 0),
                "log_loss": mv.metrics.get("log_loss", 0),
            })
        rows.sort(key=lambda x: x["f1_macro"], reverse=True)
        return rows

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _update_stage(self, version_id: str, stage: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE model_versions SET stage = ? WHERE version_id = ?",
                (stage, version_id),
            )

    def _row_to_version(self, row: tuple) -> ModelVersion:
        return ModelVersion(
            version_id=row[0],
            model_type=row[1],
            artifact_path=row[2],
            stage=row[3],
            created_at=row[4],
            description=row[5],
            metrics=json.loads(row[6]),
            config=json.loads(row[7]),
            tags=json.loads(row[8]),
        )

    def __repr__(self) -> str:
        total = len(self.list_versions())
        prod = len(self.list_versions(stage=STAGE_PRODUCTION))
        return f"ModelRegistry(total={total}, production={prod})"
