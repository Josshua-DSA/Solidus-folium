"""
Strategy Registry — Auto-discovery dan registrasi strategy.
Menghindari central switch-case saat menambah strategy baru.
"""
from typing import Dict, Optional, Type, List
from app.strategies.base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)

# Global registry
_REGISTRY: Dict[str, Type[BaseStrategy]] = {}


def register_strategy(cls: Type[BaseStrategy]) -> Type[BaseStrategy]:
    """
    Decorator untuk mendaftarkan strategy ke registry.

    Usage:
        @register_strategy
        class MomentumStrategy(BaseStrategy):
            ...
    """
    # Instantiate briefly to get the name
    # Strategy classes must accept no required args for registration
    try:
        instance = cls.__new__(cls)
        name = instance.name if hasattr(instance, 'name') else cls.__name__
    except Exception:
        name = cls.__name__

    _REGISTRY[name] = cls
    logger.debug("Registered strategy: %s", name)
    return cls


class StrategyRegistry:
    """
    Registry untuk auto-discovery trading strategies.
    """

    @staticmethod
    def get(name: str, **kwargs) -> BaseStrategy:
        """
        Get strategy instance by name.

        Args:
            name: Strategy name
            **kwargs: Constructor arguments

        Returns:
            Strategy instance

        Raises:
            KeyError: if strategy not found
        """
        if name not in _REGISTRY:
            raise KeyError(
                f"Strategy '{name}' not found. "
                f"Available: {list(_REGISTRY.keys())}"
            )
        return _REGISTRY[name](**kwargs)

    @staticmethod
    def list_strategies(tier: Optional[int] = None) -> List[str]:
        """
        List semua strategy yang terdaftar.

        Args:
            tier: Filter by tier (1 atau 2). None = semua.

        Returns:
            List nama strategy
        """
        if tier is None:
            return list(_REGISTRY.keys())

        result = []
        for name, cls in _REGISTRY.items():
            try:
                instance = cls.__new__(cls)
                if hasattr(instance, 'tier') and instance.tier == tier:
                    result.append(name)
            except Exception:
                pass
        return result

    @staticmethod
    def list_bot_eligible() -> List[str]:
        """List strategies yang boleh dipakai di bot mode (Tier 1 only)."""
        return StrategyRegistry.list_strategies(tier=1)

    def __repr__(self) -> str:
        return f"StrategyRegistry(strategies={list(_REGISTRY.keys())})"
