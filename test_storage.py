from storage import DmsStorage


def test_patient_lookup_and_request_creation(tmp_path):
    storage = DmsStorage(str(tmp_path / "test.db"))
    storage.initialize()

    patient = storage.find_patient(
        "Иванов Иван Иванович",
        "01.03.1990",
        "DMS-001-2026",
        "123-456-789 00",
    )
    assert patient is not None
    assert patient.is_active

    storage.link_vk_user(100500, patient.id)
    linked = storage.get_patient_by_vk(100500)
    assert linked is not None
    assert linked.policy_number == "DMS-001-2026"

    service = storage.get_service_by_name("Терапевт")
    clinic = storage.list_clinics(service["id"])[0]
    request_id = storage.create_request(
        vk_user_id=100500,
        patient_id=patient.id,
        service_id=service["id"],
        clinic_id=clinic["id"],
        request_type="Запись по ДМС",
        contact="+7 900 000-00-00",
        preferred_time="20.06.2026 после 15:00",
        comment="",
        status="Передано в медицинскую организацию",
    )
    assert request_id == 1
    assert storage.list_user_requests(100500)[0]["status"] == "Передано в медицинскую организацию"


def test_admin_request_without_verified_patient(tmp_path):
    storage = DmsStorage(str(tmp_path / "test.db"))
    storage.initialize()

    request_id = storage.create_request(
        vk_user_id=200600,
        patient_id=None,
        request_type="Обращение к администратору",
        contact="+7 900 000-00-00",
        preferred_time="Не указано",
        comment="Пациент не найден в системе ДМС",
        status="Передано администратору",
        patient_instruction="Ожидайте ответа администратора страховой компании.",
    )

    request = storage.list_user_requests(200600)[0]
    assert request_id == 1
    assert request["patient_id"] is None
    assert request["status"] == "Передано администратору"
