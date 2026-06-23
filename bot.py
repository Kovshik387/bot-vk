import random
import time
from dataclasses import dataclass, field

import requests
import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll

from config import get_settings
from keyboards import back_keyboard, main_keyboard, options_keyboard, start_keyboard, yes_no_keyboard
from storage import DmsStorage, Patient


DATE_HINT = "Введите дату в формате ДД.ММ.ГГГГ, например 01.03.1990."


@dataclass
class Session:
    state: str = "menu"
    data: dict = field(default_factory=dict)


class DmsVkBot:
    def __init__(self, token: str, group_id: int, storage: DmsStorage, admin_ids: tuple[int, ...] = ()):
        self.storage = storage
        self.admin_ids = admin_ids
        self.sessions: dict[int, Session] = {}
        self.vk_session = vk_api.VkApi(token=token)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkBotLongPoll(self.vk_session, group_id)

    def run(self):
        print("VK-бот навигации пациентов по ДМС запущен.")
        while True:
            try:
                for event in self.longpoll.listen():
                    if event.type == VkBotEventType.MESSAGE_NEW and event.obj.message.get("text"):
                        user_id = event.obj.message["from_id"]
                        text = event.obj.message["text"].strip()
                        self.handle_message(user_id, text)
            except requests.exceptions.RequestException as error:
                print(f"Ошибка соединения с VK Long Poll: {error}. Повтор через 10 секунд.")
                time.sleep(10)
                self.longpoll.update_longpoll_server()

    def handle_message(self, user_id: int, text: str):
        normalized = text.lower()
        if normalized in ("/start", "начать", "старт", "в главное меню"):
            self.show_menu(user_id)
            return
        if normalized == "помощь":
            self.send_help(user_id)
            return
        if normalized == "сбросить данные":
            self.storage.unlink_vk_user(user_id)
            self.sessions.pop(user_id, None)
            self.send_message(
                user_id,
                "Данные привязки удалены. Для продолжения пройдите проверку ДМС заново.",
                start_keyboard(),
            )
            return

        patient = self.storage.get_patient_by_vk(user_id)
        session = self.sessions.setdefault(user_id, Session())

        if normalized == "начать проверку дмс" or session.state.startswith("auth_"):
            self.process_auth(user_id, text, session)
            return

        if normalized == "администратор" or session.state.startswith("admin_"):
            if session.state.startswith("admin_"):
                self.process_admin_flow(user_id, text, session, patient)
            else:
                self.start_admin_request(user_id, patient)
            return

        if normalized == "статус заявки":
            self.send_request_status(user_id, patient)
            return

        if not patient:
            self.send_message(
                user_id,
                "Здравствуйте. Я бот страховой компании для навигации пациентов по ДМС.\n\n"
                "Перед показом клиник и услуг нужно проверить, что ваш полис действует. "
                "Если данные не проходят проверку или полис просрочен, отправьте обращение администратору.",
                start_keyboard(),
            )
            return

        if normalized == "проверить полис":
            self.send_policy_info(user_id, patient)
        elif normalized == "медорганизации":
            self.send_clinics(user_id)
        elif normalized == "записаться к врачу":
            self.start_service_flow(user_id, "doctor")
        elif normalized == "сдать анализы":
            self.start_service_flow(user_id, "lab")
        elif normalized == "согласование услуги":
            self.start_service_flow(user_id, "approval")
        elif session.state.startswith("service_"):
            self.process_service_flow(user_id, text, session, patient)
        else:
            self.send_message(user_id, "Выберите действие на клавиатуре.", main_keyboard())

    def show_menu(self, user_id: int):
        patient = self.storage.get_patient_by_vk(user_id)
        self.sessions[user_id] = Session()
        if patient:
            self.send_message(
                user_id,
                f"Главное меню ДМС.\n\nПациент: {patient.full_name}\nПолис: {patient.policy_number}",
                main_keyboard(),
            )
        else:
            self.send_message(
                user_id,
                "Здравствуйте. Для доступа к навигации по ДМС пройдите проверку полиса.",
                start_keyboard(),
            )

    def process_auth(self, user_id: int, text: str, session: Session):
        if session.state == "menu":
            session.state = "auth_full_name"
            session.data = {}
            self.send_message(user_id, "Введите ФИО полностью, как в договоре ДМС.", back_keyboard())
            return

        if session.state == "auth_full_name":
            session.data["full_name"] = text.strip()
            session.state = "auth_birth_date"
            self.send_message(user_id, DATE_HINT, back_keyboard())
            return

        if session.state == "auth_birth_date":
            if not self._looks_like_date(text):
                self.send_message(user_id, DATE_HINT, back_keyboard())
                return
            session.data["birth_date"] = text.strip()
            session.state = "auth_policy"
            self.send_message(user_id, "Введите номер полиса ДМС, например DMS-001-2026.", back_keyboard())
            return

        if session.state == "auth_policy":
            session.data["policy"] = text.strip()
            session.state = "auth_snils"
            self.send_message(user_id, "Введите СНИЛС в формате 123-456-789 00.", back_keyboard())
            return

        if session.state == "auth_snils":
            session.data["snils"] = text.strip()
            patient = self.storage.find_patient(
                session.data["full_name"],
                session.data["birth_date"],
                session.data["policy"],
                session.data["snils"],
            )
            if not patient:
                self.sessions[user_id] = Session()
                self.send_message(
                    user_id,
                    "Пациент не найден в системе ДМС. Проверьте данные или отправьте запрос администратору.",
                    start_keyboard(),
                )
                return
            if not patient.is_active:
                self.sessions[user_id] = Session()
                self.send_message(
                    user_id,
                    f"Полис найден, но сейчас не действует.\nСрок действия: до {patient.active_until}.\n"
                    "Для уточнения обратитесь к администратору страховой компании.",
                    start_keyboard(),
                )
                return
            self.storage.link_vk_user(user_id, patient.id)
            self.sessions[user_id] = Session()
            self.send_message(
                user_id,
                f"Проверка пройдена.\n\nПациент: {patient.full_name}\n"
                f"Программа ДМС: {patient.program}\nПолис действует до {patient.active_until}.",
                main_keyboard(),
            )

    def send_policy_info(self, user_id: int, patient: Patient):
        status = "действует" if patient.is_active else "не действует"
        self.send_message(
            user_id,
            f"Информация по ДМС:\n"
            f"Пациент: {patient.full_name}\n"
            f"Номер полиса: {patient.policy_number}\n"
            f"Программа: {patient.program}\n"
            f"Статус: {status}\n"
            f"Срок действия: до {patient.active_until}",
            main_keyboard(),
        )

    def send_clinics(self, user_id: int, service_id: int | None = None):
        clinics = self.storage.list_clinics(service_id)
        if not clinics:
            self.send_message(user_id, "По выбранной услуге медицинские организации не найдены.", main_keyboard())
            return
        lines = ["Доступные медицинские организации:"]
        for clinic in clinics:
            lines.append(
                f"\n{clinic['name']}\nАдрес: {clinic['address']}\nТелефон: {clinic['phone']}\nГрафик: {clinic['work_time']}"
            )
        self.send_message(user_id, "\n".join(lines), main_keyboard())

    def start_service_flow(self, user_id: int, category: str):
        if category == "approval":
            services = [s for s in self.storage.list_services() if s["access_type"] == "approval"]
        else:
            services = self.storage.list_services(category)
        if not services:
            self.send_message(user_id, "В справочнике пока нет услуг по выбранному направлению.", main_keyboard())
            return
        self.sessions[user_id] = Session(state="service_select", data={"category": category})
        names = [s["name"] for s in services]
        self.send_message(user_id, "Выберите услугу.", options_keyboard(names))

    def process_service_flow(self, user_id: int, text: str, session: Session, patient: Patient):
        if session.state == "service_select":
            service = self.storage.get_service_by_name(text)
            if not service:
                self.send_message(user_id, "Выберите услугу из списка.", back_keyboard())
                return
            session.data["service_id"] = service["id"]
            session.data["service_name"] = service["name"]
            session.data["access_type"] = service["access_type"]
            clinics = self.storage.list_clinics(service["id"])
            if not clinics:
                self.send_message(user_id, "Для выбранной услуги клиники не найдены. Передаю вопрос администратору.", main_keyboard())
                self.create_admin_request(user_id, patient, f"Нет клиник по услуге: {service['name']}")
                return

            clinic_names = [c["name"] for c in clinics]
            access_text = "доступна по прямому обращению" if service["access_type"] == "direct" else "требует согласования"
            session.state = "service_clinic"
            self.send_message(
                user_id,
                f"{service['description']}\n\nУслуга {access_text}. Выберите медицинскую организацию.",
                options_keyboard(clinic_names),
            )
            return

        if session.state == "service_clinic":
            clinic = self.storage.get_clinic_by_name(text)
            if not clinic:
                self.send_message(user_id, "Выберите медицинскую организацию из списка.", back_keyboard())
                return
            session.data["clinic_id"] = clinic["id"]
            session.data["clinic_name"] = clinic["name"]
            session.state = "service_time"
            self.send_message(
                user_id,
                "Укажите желаемую дату и время обращения. Например: 20.06.2026 после 15:00.",
                back_keyboard(),
            )
            return

        if session.state == "service_time":
            session.data["preferred_time"] = text.strip()
            session.state = "service_contact"
            self.send_message(user_id, "Укажите контактный телефон для подтверждения заявки.", back_keyboard())
            return

        if session.state == "service_contact":
            session.data["contact"] = text.strip()
            session.state = "service_comment"
            self.send_message(
                user_id,
                "Добавьте комментарий для администратора или напишите «Нет».",
                back_keyboard(),
            )
            return

        if session.state == "service_comment":
            comment = "" if text.lower() == "нет" else text.strip()
            access_type = session.data["access_type"]
            status = "Передано в медицинскую организацию" if access_type == "direct" else "На согласовании в страховой компании"
            request_type = "Запись по ДМС" if access_type == "direct" else "Согласование услуги"
            instruction = self.build_patient_instruction(status, session.data["clinic_name"], access_type)
            request_id = self.storage.create_request(
                vk_user_id=user_id,
                patient_id=patient.id,
                service_id=session.data["service_id"],
                clinic_id=session.data["clinic_id"],
                request_type=request_type,
                contact=session.data["contact"],
                preferred_time=session.data["preferred_time"],
                comment=comment,
                status=status,
                patient_instruction=instruction,
            )
            self.notify_admins(
                f"Новая заявка #{request_id}\n"
                f"Пациент: {patient.full_name}\n"
                f"Услуга: {session.data['service_name']}\n"
                f"Клиника: {session.data['clinic_name']}\n"
                f"Статус: {status}\n"
                f"Контакт: {session.data['contact']}"
            )
            self.sessions[user_id] = Session()
            self.send_message(
                user_id,
                f"Заявка #{request_id} создана.\nСтатус: {status}.\n\n"
                f"Инструкция: {instruction}\n\n"
                "Бот не выполняет медицинскую консультацию. По срочным вопросам обращайтесь в экстренные службы.",
                main_keyboard(),
            )

    def start_admin_request(self, user_id: int, patient: Patient | None = None):
        self.sessions[user_id] = Session(
            state="admin_question",
            data={"patient_id": patient.id if patient else None, "patient_name": patient.full_name if patient else "Не идентифицирован"},
        )
        if patient:
            prompt = "Опишите вопрос для администратора страховой компании."
        else:
            prompt = (
                "Опишите вопрос для администратора страховой компании. Например: пациент не найден в системе ДМС, "
                "полис просрочен или данные указаны верно, но проверка не проходит."
            )
        self.send_message(user_id, prompt, back_keyboard())

    def process_admin_flow(self, user_id: int, text: str, session: Session, patient: Patient | None):
        if session.state == "admin_question":
            session.data["question"] = text.strip()
            session.state = "admin_contact"
            self.send_message(user_id, "Укажите телефон или другой контакт для ответа.", back_keyboard())
            return

        if session.state == "admin_contact":
            request_id = self.storage.create_request(
                vk_user_id=user_id,
                patient_id=patient.id if patient else session.data.get("patient_id"),
                request_type="Обращение к администратору",
                contact=text.strip(),
                preferred_time="Не указано",
                comment=session.data["question"],
                status="Передано администратору",
                patient_instruction="Ожидайте ответа администратора страховой компании. Специалист свяжется с вами по указанному контакту.",
            )
            self.notify_admins(
                f"Обращение к администратору #{request_id}\n"
                f"Пациент: {patient.full_name if patient else session.data.get('patient_name', 'Не идентифицирован')}\n"
                f"VK ID: {user_id}\n"
                f"Вопрос: {session.data['question']}\n"
                f"Контакт: {text.strip()}"
            )
            self.sessions[user_id] = Session()
            keyboard = main_keyboard() if patient else start_keyboard()
            self.send_message(user_id, f"Обращение #{request_id} передано администратору.", keyboard)

    def create_admin_request(self, user_id: int, patient: Patient, comment: str):
        request_id = self.storage.create_request(
            vk_user_id=user_id,
            patient_id=patient.id,
            request_type="Автоматическая передача администратору",
            contact="Не указан",
            preferred_time="Не указано",
            comment=comment,
            status="Передано администратору",
            patient_instruction="Обращение передано администратору. Дождитесь ответа специалиста страховой компании.",
        )
        self.notify_admins(f"Автоматическое обращение #{request_id}\nПациент: {patient.full_name}\n{comment}")

    def send_request_status(self, user_id: int, patient: Patient | None = None):
        requests = self.storage.list_user_requests(user_id)
        if not requests:
            self.send_message(user_id, "У вас пока нет заявок.", main_keyboard() if patient else start_keyboard())
            return
        lines = ["Последние заявки:"]
        for item in requests:
            service = item["service_name"] or item["request_type"]
            clinic = item["clinic_name"] or "не выбрана"
            instruction = item["patient_instruction"] or "Инструкция пока не сформирована. Дождитесь обработки заявки администратором."
            lines.append(
                f"\n#{item['id']} - {service}\nКлиника: {clinic}\nСтатус: {item['status']}\n"
                f"Инструкция: {instruction}\nСоздана: {item['created_at']}"
            )
        self.send_message(user_id, "\n".join(lines), main_keyboard() if patient else start_keyboard())

    @staticmethod
    def build_patient_instruction(status: str, clinic_name: str, access_type: str) -> str:
        if access_type == "direct":
            return (
                f"Услуга доступна по прямому обращению. Позвоните в {clinic_name} для подтверждения времени "
                "или обратитесь в регистратуру с паспортом и полисом ДМС."
            )
        return (
            "Заявка направлена на согласование в страховую компанию. После одобрения в статусе появится "
            f"конкретная инструкция: куда обратиться, в какую клинику записаться и какие документы взять."
        )

    def send_help(self, user_id: int):
        self.send_message(
            user_id,
            "Я помогаю пациенту пройти организационный маршрут по ДМС: проверить полис, выбрать услугу, "
            "посмотреть доступные медицинские организации, создать заявку на запись или согласование.\n\n"
            "Я не ставлю диагнозы, не назначаю лечение и не храню медицинские документы.",
            start_keyboard(),
        )

    def notify_admins(self, text: str):
        for admin_id in self.admin_ids:
            self.send_message(admin_id, text, None)

    def send_message(self, user_id: int, message: str, keyboard: str | None = None):
        payload = {
            "user_id": user_id,
            "message": message,
            "random_id": random.randint(1, 2_147_483_647),
        }
        if keyboard:
            payload["keyboard"] = keyboard
        self.vk.messages.send(**payload)

    @staticmethod
    def _looks_like_date(text: str) -> bool:
        parts = text.strip().split(".")
        return len(parts) == 3 and all(part.isdigit() for part in parts) and len(parts[2]) == 4


def main():
    settings = get_settings()
    storage = DmsStorage(settings.db_path)
    storage.initialize()
    bot = DmsVkBot(settings.vk_token, settings.group_id, storage, settings.admin_ids)
    bot.run()


if __name__ == "__main__":
    main()
