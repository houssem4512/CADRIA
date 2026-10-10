from django.contrib import admin
from .models import AgentDefinition, AgentRun, AssignmentSuggestion, Proposal

admin.site.register(AgentDefinition)
admin.site.register(AgentRun)
admin.site.register(Proposal)
admin.site.register(AssignmentSuggestion)
