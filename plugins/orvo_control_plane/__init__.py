"""Orvo ecommerce operations control-plane primitives.

This package keeps product control-plane business logic out of transport
adapters. Runtime execution is driven from connector contracts registered here,
then adapters only translate a compiled call to a concrete integration.
"""

from .runtime import (  # noqa: F401
    ConnectorAuditEvent,
    ConnectorContract,
    ConnectorContractViolation,
    ConnectorExecutionRequest,
    ConnectorExecutor,
    ConnectorOutcome,
    ConnectorRegistry,
    ConnectorResult,
    ConnectorRunLedger,
    ConnectorRunSummary,
    CompiledConnectorCall,
    compile_connector_call,
)
