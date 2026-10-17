from django.contrib import admin

from .models import Option, Poll, Vote


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "created_at")
    inlines = [OptionInline]


admin.site.register(Vote)
