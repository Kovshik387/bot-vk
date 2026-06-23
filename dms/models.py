from django.db import models


class Patient(models.Model):
    full_name = models.CharField("ФИО", max_length=255)
    birth_date = models.CharField("Дата рождения", max_length=10)
    policy_number = models.CharField("Номер полиса", max_length=64, unique=True)
    snils = models.CharField("СНИЛС", max_length=32)
    program = models.CharField("Программа ДМС", max_length=128)
    active_until = models.CharField("Действует до", max_length=10)
    is_active = models.BooleanField("Полис активен")

    class Meta:
        managed = False
        db_table = "patients"
        verbose_name = "пациент"
        verbose_name_plural = "пациенты"
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.policy_number})"


class Service(models.Model):
    ACCESS_CHOICES = [
        ("direct", "Прямой доступ"),
        ("approval", "Требует согласования"),
    ]
    CATEGORY_CHOICES = [
        ("doctor", "Врач"),
        ("lab", "Анализы"),
        ("diagnostic", "Диагностика"),
    ]

    name = models.CharField("Название услуги", max_length=255, unique=True)
    category = models.CharField("Категория", max_length=32, choices=CATEGORY_CHOICES)
    access_type = models.CharField("Тип доступа", max_length=32, choices=ACCESS_CHOICES)
    description = models.TextField("Описание для пациента")

    class Meta:
        managed = False
        db_table = "services"
        verbose_name = "услуга ДМС"
        verbose_name_plural = "услуги ДМС"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class Clinic(models.Model):
    name = models.CharField("Название", max_length=255)
    address = models.CharField("Адрес", max_length=255)
    phone = models.CharField("Телефон", max_length=64)
    work_time = models.CharField("График работы", max_length=255)

    class Meta:
        managed = False
        db_table = "clinics"
        verbose_name = "медицинская организация"
        verbose_name_plural = "медицинские организации"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ClinicService(models.Model):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, verbose_name="Медицинская организация")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name="Услуга")

    class Meta:
        managed = False
        db_table = "clinic_services"
        verbose_name = "услуга в медорганизации"
        verbose_name_plural = "услуги в медорганизациях"
        unique_together = ("clinic", "service")
        ordering = ["clinic__name", "service__name"]

    def __str__(self):
        return f"{self.clinic} - {self.service}"


class UserLink(models.Model):
    vk_user_id = models.IntegerField("VK ID", primary_key=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Пациент")
    linked_at = models.CharField("Дата привязки", max_length=32)

    class Meta:
        managed = False
        db_table = "user_links"
        verbose_name = "привязка VK"
        verbose_name_plural = "привязки VK"
        ordering = ["-linked_at"]

    def __str__(self):
        return f"{self.vk_user_id} - {self.patient}"


class Request(models.Model):
    STATUS_CHOICES = [
        ("Передано администратору", "Передано администратору"),
        ("На согласовании в страховой компании", "На согласовании в страховой компании"),
        ("Одобрено", "Одобрено"),
        ("Передано в медицинскую организацию", "Передано в медицинскую организацию"),
        ("Требуется уточнение данных", "Требуется уточнение данных"),
        ("Отклонено", "Отклонено"),
        ("Завершено", "Завершено"),
    ]

    vk_user_id = models.IntegerField("VK ID")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, verbose_name="Пациент")
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Услуга")
    clinic = models.ForeignKey(Clinic, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Медорганизация")
    request_type = models.CharField("Тип заявки", max_length=128)
    contact = models.CharField("Контакт", max_length=128)
    preferred_time = models.CharField("Желаемое время", max_length=255)
    comment = models.TextField("Комментарий", blank=True)
    status = models.CharField("Статус", max_length=128, choices=STATUS_CHOICES)
    patient_instruction = models.TextField("Инструкция пациенту", blank=True)
    created_at = models.CharField("Создана", max_length=32)
    updated_at = models.CharField("Обновлена", max_length=32)

    class Meta:
        managed = False
        db_table = "requests"
        verbose_name = "заявка"
        verbose_name_plural = "заявки"
        ordering = ["-id"]

    def __str__(self):
        return f"Заявка #{self.id}: {self.request_type}"
