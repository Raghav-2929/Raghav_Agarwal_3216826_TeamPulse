"""Shared microservice chassis for TeamPulse.

Every service is built from the same parts so cross-cutting concerns (JWT auth, structured logging,
problem+json errors, outbox/inbox messaging, circuit breakers, tracing, health checks) behave the
same way everywhere. Domain code never lives here.
"""

__version__ = "1.0.0"
