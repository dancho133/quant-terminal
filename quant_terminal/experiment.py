"""Canonical experiment identity and fixed, non-selective robustness reruns."""

from __future__ import annotations

import hashlib
import json
import logging
import platform
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from quant_terminal import __version__
from quant_terminal.backtest import simulate
from quant_terminal.critic import review
from quant_terminal.data import dataset_from_bars, load_dataset
from quant_terminal.features import FeatureRow
from quant_terminal.models import CostModel, Dataset, ExperimentConfig
from quant_terminal.strategies import make_strategy

LOGGER = logging.getLogger(__name__)
ENGINE_FILES = (
    "__init__.py",
    "models.py",
    "data.py",
    "features.py",
    "strategies.py",
    "risk.py",
    "backtest.py",
    "critic.py",
    "experiment.py",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def engine_fingerprint() -> dict[str, Any]:
    root = Path(__file__).parent
    files = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ENGINE_FILES}
    return {"sha256": hashlib.sha256(canonical_json(files).encode()).hexdigest(), "files": files}


def normalized_config(config: ExperimentConfig) -> ExperimentConfig:
    strategy = make_strategy(config.strategy, config.params)

    def continuous(value: int | float) -> float:
        return float(value) if value != 0 else 0.0

    params = {
        key: value if key in ("fast", "slow", "lookback") else continuous(value)
        for key, value in strategy.params.items()
    }
    return replace(
        config,
        initial_capital=continuous(config.initial_capital),
        params=params,
        risk=replace(
            config.risk, **{key: continuous(value) for key, value in asdict(config.risk).items()}
        ),
        costs=replace(
            config.costs, **{key: continuous(value) for key, value in asdict(config.costs).items()}
        ),
    )


def experiment_identity(
    config: ExperimentConfig, dataset: Dataset, engine_hash: str | None = None
) -> str:
    payload = {
        "schema_version": 1,
        "engine_version": __version__,
        "engine_sha256": engine_hash or engine_fingerprint()["sha256"],
        "config": asdict(normalized_config(config)),
        "dataset": {
            "asset": dataset.asset,
            "sha256": dataset.sha256,
            "provenance": dataset.provenance,
        },
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()[:20]


@dataclass(frozen=True)
class ConstantLong:
    name: str = "constant_long_comparator"
    params: dict[str, int | float] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", {})

    def target(self, feature: FeatureRow, current_weight: float) -> float:
        return 0.4


def run_experiment(config: ExperimentConfig, dataset: Dataset | None = None) -> dict[str, Any]:
    config = normalized_config(config)
    dataset = dataset or load_dataset(config.asset)
    verified = dataset_from_bars(dataset.asset, dataset.bars, dataset.provenance)
    if verified.sha256 != dataset.sha256:
        raise ValueError("Dataset identity does not match its bars.")
    strategy = make_strategy(config.strategy, config.params)
    base = simulate(dataset, strategy, config)
    comparator = simulate(dataset, ConstantLong(), config)
    base["metrics"]["same_risk_benchmark_return"] = comparator["metrics"]["total_return"]
    base["metrics"]["asset_concentration"] = 1.0 if base["fills"] else 0.0
    selected = [
        b
        for b in dataset.bars
        if config.evaluation_start <= b.timestamp.date().isoformat() <= config.evaluation_end
    ]
    if any(v * 2 >= 10_000 for v in (config.costs.fee_bps, config.costs.slippage_bps)):
        raise ValueError(
            "Base fees and slippage must be below 5000 bps to evaluate doubled-cost stress."
        )
    cost_scenarios = []
    for name, factor in (("zero_cost", 0), ("base_cost", 1), ("double_cost", 2)):
        outcome = (
            base
            if factor == 1
            else simulate(
                dataset,
                make_strategy(config.strategy, config.params),
                replace(
                    config,
                    costs=CostModel(
                        config.costs.fee_bps * factor, config.costs.slippage_bps * factor
                    ),
                ),
            )
        )
        cost_scenarios.append({"name": name, "cost_multiplier": factor, **outcome["metrics"]})
    key = "fast" if config.strategy == "momentum" else "lookback"
    original = int(config.params[key])
    variants = []
    for factor in (0.8, 1.2):
        value = max(2, round(original * factor))
        if key == "fast":
            value = min(value, int(config.params["slow"]) - 1)
        params = config.params | {key: value}
        outcome = simulate(
            dataset, make_strategy(config.strategy, params), replace(config, params=params)
        )
        variants.append(
            {
                "changed_parameter": key,
                "nominal_multiplier": factor,
                "params": params,
                **outcome["metrics"],
            }
        )
    windows = []
    if len(selected) >= 4:
        mid = len(selected) // 2
        for name, bars in (("first_half", selected[:mid]), ("second_half", selected[mid:])):
            window_config = replace(
                config,
                evaluation_start=bars[0].timestamp.date().isoformat(),
                evaluation_end=bars[-1].timestamp.date().isoformat(),
            )
            outcome = simulate(
                dataset, make_strategy(config.strategy, config.params), window_config
            )
            windows.append(
                {
                    "name": name,
                    "start": window_config.evaluation_start,
                    "end": window_config.evaluation_end,
                    **outcome["metrics"],
                }
            )
    robustness = {
        "cost_scenarios": cost_scenarios,
        "parameter_variants": variants,
        "time_windows": windows,
        "retrospective_selection": True,
        "method": "Fixed +/-20% neighboring window parameters; base/zero/double costs; chronological half-window resets. Prior bars supply feature warm-up. No best variant selection.",
    }
    critic = review(base, robustness)
    engine = engine_fingerprint()
    identity = experiment_identity(config, dataset, engine["sha256"])
    LOGGER.info(
        canonical_json(
            {
                "event": "experiment_completed",
                "experiment_id": identity,
                "strategy": strategy.name,
                "verdict": critic["verdict"],
            }
        )
    )
    return {
        "schema_version": 1,
        "experiment_id": identity,
        "engine_version": __version__,
        "engine": engine,
        "config": asdict(config),
        "reproducibility": {
            "python": platform.python_version(),
            "randomness": "none",
            "numeric_engine": "Python standard library",
            "identity_method": "SHA-256(config + normalized OHLCV + provenance + numerical source hashes), first 20 hex characters",
        },
        "dataset": {
            "asset": dataset.asset,
            "interval": "1d",
            "rows": len(dataset.bars),
            "start": dataset.bars[0].timestamp.isoformat(),
            "end": dataset.bars[-1].timestamp.isoformat(),
            "sha256": dataset.sha256,
            "provenance": dataset.provenance,
            "evaluation_start": selected[0].timestamp.isoformat(),
            "evaluation_end": selected[-1].timestamp.isoformat(),
            "prior_context_bars": sum(b.timestamp < selected[0].timestamp for b in dataset.bars),
        },
        "strategy": {
            "name": strategy.name,
            "hypothesis": strategy.hypothesis,
            "assumptions": list(strategy.assumptions),
            "failure_modes": list(strategy.failure_modes),
            "entry_exit": "40% target or cash, daily rebalance; independent risk may cap to 25% by default.",
            "parameters": strategy.params,
        },
        "result": base,
        "comparator": comparator,
        "robustness": robustness,
        "critic": critic,
        "scope": {
            "execution": "historical simulated fills only",
            "agents": "protocols only; no LLM connected",
            "dataset": dataset.provenance.get("kind", "unknown"),
            "financial_advice": False,
        },
    }
