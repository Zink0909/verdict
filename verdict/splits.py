"""Time-ordered splits and the sealed-holdout ledger.

Random cross-validation on financial time series leaks the future into training
and manufactures edges that do not exist. This module therefore offers **no**
shuffled-split API: there is nothing to call even if you wanted one.

The sealed holdout is enforced as a state machine backed by an on-disk ledger.
Every unseal is stamped with the time, the reason, and a fingerprint of the
analysis configuration. Unsealing again under a *different* fingerprint — the
sin of adjusting the model and looking a second time — raises. Re-running the
identical evaluation is recorded as a reproduction rather than blocked, because
reproducibility must not be punished.

Provenance: chart_cnn/chartcnn/splits.py (three-block chronological split),
generalized; the ledger is new to the framework.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# three-block chronological split
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TimeSplit:
    """Three disjoint, strictly increasing blocks of positional indices."""
    train: np.ndarray
    valid: np.ndarray
    holdout: np.ndarray
    train_end: pd.Timestamp
    valid_end: pd.Timestamp
    holdout_start: pd.Timestamp

    @property
    def sizes(self) -> dict:
        return {"train": int(len(self.train)), "valid": int(len(self.valid)),
                "holdout": int(len(self.holdout))}


def time_splits(dates, train_end, valid_end, holdout_start=None) -> TimeSplit:
    """Split observations into train / validation / holdout **by date only**.

    train   : date <= train_end
    valid   : train_end < date <= valid_end
    holdout : date >= holdout_start (default: the day after valid_end)

    Keeping the holdout untouched until the end is a matter of process; this
    function gives it a name and a boundary, `SealedHoldout` gives it teeth.
    """
    dates = pd.to_datetime(pd.Index(dates))
    train_end = pd.Timestamp(train_end)
    valid_end = pd.Timestamp(valid_end)
    if holdout_start is None:
        holdout_start = valid_end + pd.Timedelta(days=1)
    holdout_start = pd.Timestamp(holdout_start)
    if not (train_end < valid_end <= holdout_start):
        raise ValueError(
            "boundaries must satisfy train_end < valid_end <= holdout_start, got "
            f"{train_end.date()}, {valid_end.date()}, {holdout_start.date()}")
    pos = np.arange(len(dates))
    return TimeSplit(
        train=pos[dates <= train_end],
        valid=pos[(dates > train_end) & (dates <= valid_end)],
        holdout=pos[dates >= holdout_start],
        train_end=train_end, valid_end=valid_end, holdout_start=holdout_start)


def assert_no_leakage(split: TimeSplit) -> None:
    """Independent assertion that the blocks are disjoint and time-ordered."""
    s_tr, s_va, s_ho = (set(split.train.tolist()), set(split.valid.tolist()),
                        set(split.holdout.tolist()))
    if s_tr & s_va or s_tr & s_ho or s_va & s_ho:
        raise AssertionError("split blocks overlap — leakage")
    if len(split.train) and len(split.valid) and split.train.max() >= split.valid.min():
        raise AssertionError("train indices are not strictly before valid")
    if len(split.valid) and len(split.holdout) and split.valid.max() >= split.holdout.min():
        raise AssertionError("valid indices are not strictly before holdout")


# --------------------------------------------------------------------------
# walk-forward
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Fold:
    train: np.ndarray
    test: np.ndarray


def walk_forward(dates, n_folds: int = 5, min_train: int | None = None,
                 expanding: bool = True) -> list[Fold]:
    """Walk-forward folds: every test block sits strictly after its training data.

    The tail of the sample after `min_train` observations is cut into `n_folds`
    contiguous test blocks. With `expanding=True` the training set grows to
    include everything before the test block; with `expanding=False` it is a
    rolling window of `min_train` observations.
    """
    n = len(pd.Index(dates))
    if min_train is None:
        min_train = max(1, n // (n_folds + 1))
    if min_train >= n:
        raise ValueError("min_train must leave observations for testing")
    edges = np.linspace(min_train, n, n_folds + 1).astype(int)
    folds = []
    for i in range(n_folds):
        lo, hi = edges[i], edges[i + 1]
        if hi <= lo:
            continue
        train_lo = 0 if expanding else max(0, lo - min_train)
        folds.append(Fold(train=np.arange(train_lo, lo), test=np.arange(lo, hi)))
    return folds


# --------------------------------------------------------------------------
# sealed holdout
# --------------------------------------------------------------------------

class HoldoutAlreadyUnsealed(RuntimeError):
    """Raised when a sealed holdout is opened a second time under a new setup."""


def fingerprint(config) -> str:
    """Stable short hash of an analysis configuration (dict, str, or list)."""
    blob = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


@dataclass
class SealedHoldout:
    """A holdout block whose every opening is recorded in a ledger on disk.

    The ledger — not an honour system — is what makes "looked at it once"
    checkable by a reader who was not there.
    """
    name: str
    ledger_path: Path | str
    _path: Path = field(init=False, repr=False)

    def __post_init__(self):
        self._path = Path(self.ledger_path)

    def records(self) -> list[dict]:
        if not self._path.exists():
            return []
        return [r for r in json.loads(self._path.read_text()) if r["name"] == self.name]

    @property
    def is_sealed(self) -> bool:
        return len(self.records()) == 0

    def unseal(self, reason: str, config) -> dict:
        """Open the holdout for evaluation, recording the act.

        Raises `HoldoutAlreadyUnsealed` if it was already opened under a
        different configuration fingerprint. An identical fingerprint is a
        reproduction of the same final evaluation and is allowed, counted, and
        reported as such.
        """
        fp = fingerprint(config)
        prior = self.records()
        if prior and prior[0]["fingerprint"] != fp:
            raise HoldoutAlreadyUnsealed(
                f"holdout '{self.name}' was already unsealed on {prior[0]['utc']} "
                f"under fingerprint {prior[0]['fingerprint']}; this run has "
                f"fingerprint {fp}. Changing the setup and looking again is the "
                "one thing a sealed holdout exists to prevent.")
        record = {"name": self.name, "reason": reason, "fingerprint": fp,
                  "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "kind": "first-unseal" if not prior else "reproduction"}
        allr = json.loads(self._path.read_text()) if self._path.exists() else []
        allr.append(record)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(allr, indent=2))
        return record

    def summary(self) -> str:
        """One line for the verdict report's provenance section."""
        recs = self.records()
        if not recs:
            return f"holdout '{self.name}': still sealed, never evaluated"
        first = recs[0]
        reps = len(recs) - 1
        tail = f"; {reps} identical re-run(s) since" if reps else ""
        return (f"holdout '{self.name}': unsealed once on {first['utc']} "
                f"({first['reason']}, fingerprint {first['fingerprint']}){tail}")
