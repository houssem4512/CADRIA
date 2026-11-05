from rest_framework import serializers

from accounts.serializers import UserListSerializer

from .models import AgentDefinition, AgentRun, AssignmentSuggestion, Proposal


class AgentDefinitionSerializer(serializers.ModelSerializer):
    success_rate = serializers.FloatField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = AgentDefinition
        fields = [
            "id", "key", "name", "short_name", "description", "icon", "color", "state",
            "suggested_model", "suggested_stack", "runtime_endpoint",
            "requires_human_validation", "capabilities", "input_schema_hint",
            "output_schema_hint", "total_runs", "successful_runs", "failed_runs",
            "avg_latency_ms", "last_run_at", "success_rate", "is_available", "order",
        ]


class AgentRunSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.name", read_only=True)
    agent_key = serializers.CharField(source="agent.key", read_only=True)
    agent_color = serializers.CharField(source="agent.color", read_only=True)
    agent_icon = serializers.CharField(source="agent.icon", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_reference = serializers.CharField(source="project.reference", read_only=True)
    triggered_by_name = serializers.CharField(source="triggered_by.full_name", read_only=True)
    duration_display = serializers.CharField(read_only=True)

    class Meta:
        model = AgentRun
        fields = [
            "id", "project", "project_name", "project_reference", "agent", "agent_key",
            "agent_name", "agent_color", "agent_icon", "parent_run", "triggered_by",
            "triggered_by_name", "trigger", "status", "step", "progress", "input_payload",
            "output_payload", "error_message", "tokens_in", "tokens_out", "cost_estimate",
            "started_at", "finished_at", "latency_ms", "created_at", "duration_display",
        ]
        read_only_fields = ["id", "created_at"]


class AssignmentSuggestionSerializer(serializers.ModelSerializer):
    candidate_detail = UserListSerializer(source="candidate", read_only=True)
    load_delta = serializers.FloatField(read_only=True)

    class Meta:
        model = AssignmentSuggestion
        fields = ["id", "proposal", "task_ref", "task_title", "candidate", "candidate_detail",
                  "match_score", "rationale", "matched_skills", "workload_before_hours",
                  "workload_after_hours", "accepted", "load_delta", "created_at"]


class ProposalSerializer(serializers.ModelSerializer):
    tasks_count = serializers.IntegerField(read_only=True)
    lots_count = serializers.IntegerField(read_only=True)
    assignments = AssignmentSuggestionSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_reference = serializers.CharField(source="project.reference", read_only=True)
    validated_by_name = serializers.CharField(source="validated_by.full_name", read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id", "run", "project", "project_name", "project_reference", "title", "summary",
            "status", "version", "lots_payload", "tasks_payload", "sprints_payload",
            "risks_payload", "assumptions", "total_estimate_hours", "confidence",
            "estimated_end_date", "validated_by", "validated_by_name", "validated_at",
            "rejection_reason", "created_at", "tasks_count", "lots_count", "assignments",
        ]
        read_only_fields = ["id", "created_at"]
