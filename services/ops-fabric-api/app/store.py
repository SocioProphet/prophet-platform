from __future__ import annotations

from app.models import ActionProposal, SearchRecord, TelemetryEvent


class OpsFabricStore:
    def __init__(self) -> None:
        self.events: dict[str, TelemetryEvent] = {}
        self.proposals: dict[str, ActionProposal] = {}

    def add_event(self, event: TelemetryEvent) -> TelemetryEvent:
        self.events[event.event_id] = event
        return event

    def list_events(self) -> list[TelemetryEvent]:
        return list(self.events.values())

    def add_proposal(self, proposal: ActionProposal) -> ActionProposal:
        self.proposals[proposal.proposal_id] = proposal
        return proposal

    def get_proposal(self, proposal_id: str) -> ActionProposal | None:
        return self.proposals.get(proposal_id)

    def list_proposals(self) -> list[ActionProposal]:
        return list(self.proposals.values())

    def search_records(self) -> list[SearchRecord]:
        records: list[SearchRecord] = []
        for proposal in self.proposals.values():
            records.append(
                SearchRecord(
                    result_id=proposal.proposal_id,
                    entity_type="ACTION_PROPOSAL",
                    title=proposal.summary,
                    text=" ".join(proposal.rationale),
                    target_ref=proposal.target.id,
                    evidence_ref_ids=[ref.evidence_id for ref in proposal.evidence_refs],
                    intelligence_ref_ids=[ref.intelligence_id for ref in proposal.intelligence_refs],
                    final_score=proposal.impact_estimate.confidence,
                )
            )
        for event in self.events.values():
            records.append(
                SearchRecord(
                    result_id=event.event_id,
                    entity_type="TELEMETRY_EVENT",
                    title=f"{event.event_type} for {event.subject.id}",
                    text=f"{event.event_type} {event.subject.id}",
                    target_ref=event.subject.id,
                    evidence_ref_ids=[ref.evidence_id for ref in event.evidence_refs],
                    intelligence_ref_ids=[ref.intelligence_id for ref in event.intelligence_refs],
                    final_score=1.0,
                )
            )
        return records


store = OpsFabricStore()
