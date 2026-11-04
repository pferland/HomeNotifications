"""Base class for all home notification features."""

from __future__ import annotations

import logging
from typing import Optional
from home_notifications.config import AppConfig, FeatureConfig
from home_notifications.notifier import NotificationDispatcher
from home_notifications.state import StateManager

logger = logging.getLogger(__name__)


class BaseFeature:
    """Abstract base class for scheduled features and monitors."""

    def __init__(
        self,
        name: str,
        config: AppConfig,
        state: StateManager,
        notifier: NotificationDispatcher,
    ):
        self.name = name
        self.config = config
        self.state = state
        self.notifier = notifier
        self._feature_config: Optional[FeatureConfig] = None

    @property
    def feature_config(self) -> FeatureConfig:
        if self.config:
            return self.config.get_feature(self.name)
        if self._feature_config:
            return self._feature_config
        return FeatureConfig(name=self.name, enabled=False)

    @feature_config.setter
    def feature_config(self, val: FeatureConfig) -> None:
        self._feature_config = val

    @property
    def is_enabled(self) -> bool:
        return self.feature_config.enabled

    async def execute(self) -> None:
        """Run feature check cycle."""
        raise NotImplementedError
