"""Provider-independent billing boundary; never enables or configures a provider."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID
from factlens.budget import reserve_usage, settle_usage

T = TypeVar('T')
STAGES = {'transcribe', 'extract', 'search'}

class BudgetDenied(RuntimeError):
    pass

class InvalidUsage(RuntimeError):
    pass

@dataclass(frozen=True)
class ChargedResult(Generic[T]):
    value: T
    # None means billing is unknown, including possibly billed failed requests.
    actual_micros: int | None

def positive_integer(value: object) -> bool:
    return type(value) is int and 0 < value <= 2**63 - 1

class BudgetedCall:
    def __init__(self, job_id: UUID, *, job_limit: int, month_limit: int,
                 reserve: Callable = reserve_usage, settle: Callable = settle_usage):
        if not positive_integer(job_limit) or not positive_integer(month_limit):
            raise ValueError('BUDGET_CONFIGURATION_REQUIRED')
        self.job_id = job_id
        self.job_limit, self.month_limit = job_limit, month_limit
        self._reserve, self._settle = reserve, settle
        self._records: list[dict] = []
        self._blocked = False

    def run(self, stage: str, max_cost_micros: int, operation: Callable[[], ChargedResult[T]]) -> T:
        if stage not in STAGES or not positive_integer(max_cost_micros):
            raise ValueError('INVALID_PRICE_BOUND')
        if self._blocked:
            raise BudgetDenied('BILLING_REVIEW_REQUIRED')
        reservation = self._reserve(self.job_id, max_cost_micros,
                                    job_limit=self.job_limit, month_limit=self.month_limit)
        if reservation is None:
            raise BudgetDenied('BUDGET_EXCEEDED')
        record = {'stage': stage, 'reserved': max_cost_micros, 'actual': None}
        self._records.append(record)
        # Errors do not release the reservation or trigger a retry: a timeout can be billed.
        result = operation()
        if not isinstance(result, ChargedResult):
            raise InvalidUsage('INVALID_USAGE_RECEIPT')
        actual = result.actual_micros
        if actual is None:
            return result.value
        if type(actual) is not int or not 0 <= actual <= 2**63 - 1:
            raise InvalidUsage('INVALID_USAGE_RECEIPT')
        # Record any known overrun truthfully and stop future calls; never pretend it was capped.
        record['actual'] = actual
        if actual > max_cost_micros:
            self._blocked = True
        self._settle(reservation, actual)
        if self._blocked:
            raise InvalidUsage('PRICE_BOUND_EXCEEDED')
        return result.value

    def usage(self) -> dict:
        return {'billing': 'metered', 'currencyUnit': 'configured_currency_micros',
                'actualMicros': sum(r['actual'] for r in self._records if r['actual'] is not None),
                'unknownUsageCalls': sum(r['actual'] is None for r in self._records),
                'conservativeMicros': sum(r['reserved'] if r['actual'] is None else r['actual'] for r in self._records),
                'calls': len(self._records)}

class BudgetedProviders:
    """Adapter for a selected SDK returning ChargedResult for every charged call.

    The caller must supply documented price-derived upper bounds and currency.
    This class does not supply any defaults, API keys, SDK, or network request.
    """
    def __init__(self, provider, billing: BudgetedCall, *, max_call_micros: dict[str, int]):
        if set(max_call_micros) != STAGES or not all(positive_integer(v) for v in max_call_micros.values()):
            raise ValueError('PRICE_BOUNDS_REQUIRED')
        self._provider, self._billing = provider, billing
        self._bounds = dict(max_call_micros)

    def transcribe(self, path):
        return self._billing.run('transcribe', self._bounds['transcribe'], lambda: self._provider.transcribe(path))

    def extract(self, segments):
        return self._billing.run('extract', self._bounds['extract'], lambda: self._provider.extract(segments))

    def search(self, claim):
        return self._billing.run('search', self._bounds['search'], lambda: self._provider.search(claim))

    def usage(self) -> dict:
        return self._billing.usage()
