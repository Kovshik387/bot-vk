from django.contrib import admin

from .models import Clinic, ClinicService, Patient, Request, Service, UserLink


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "policy_number", "program", "active_until", "is_active")
    list_filter = ("is_active", "program")
    search_fields = ("full_name", "policy_number", "snils")
    list_editable = ("is_active",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "access_type")
    list_filter = ("category", "access_type")
    search_fields = ("name", "description")


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "phone", "work_time")
    search_fields = ("name", "address", "phone")


@admin.register(ClinicService)
class ClinicServiceAdmin(admin.ModelAdmin):
    list_display = ("clinic", "service")
    list_filter = ("clinic", "service__category", "service__access_type")
    search_fields = ("clinic__name", "service__name")
    autocomplete_fields = ("clinic", "service")


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "request_type", "service", "clinic", "status", "short_instruction", "created_at")
    list_filter = ("status", "request_type", "service__access_type")
    search_fields = ("patient__full_name", "patient__policy_number", "contact", "comment", "patient_instruction", "vk_user_id")
    autocomplete_fields = ("patient", "service", "clinic")
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Пациент и обращение", {
            "fields": ("vk_user_id", "patient", "request_type", "service", "clinic", "contact", "preferred_time", "comment")
        }),
        ("Обработка страховой компанией", {
            "fields": ("status", "patient_instruction", "created_at", "updated_at")
        }),
    )

    @admin.display(description="Инструкция")
    def short_instruction(self, obj):
        if not obj.patient_instruction:
            return "не задана"
        return obj.patient_instruction[:80] + ("..." if len(obj.patient_instruction) > 80 else "")


@admin.register(UserLink)
class UserLinkAdmin(admin.ModelAdmin):
    list_display = ("vk_user_id", "patient", "linked_at")
    search_fields = ("vk_user_id", "patient__full_name", "patient__policy_number")
    autocomplete_fields = ("patient",)
