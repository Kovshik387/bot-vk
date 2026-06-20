from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def _button_rows(rows):
    keyboard = VkKeyboard(one_time=False)
    for row_index, row in enumerate(rows):
        if row_index:
            keyboard.add_line()
        for text, color in row:
            keyboard.add_button(text, color=color)
    return keyboard.get_keyboard()


def start_keyboard():
    return _button_rows([
        [("Начать проверку ДМС", VkKeyboardColor.PRIMARY)],
        [("Помощь", VkKeyboardColor.SECONDARY)],
    ])


def main_keyboard():
    return _button_rows([
        [("Проверить полис", VkKeyboardColor.PRIMARY), ("Медорганизации", VkKeyboardColor.SECONDARY)],
        [("Записаться к врачу", VkKeyboardColor.POSITIVE), ("Сдать анализы", VkKeyboardColor.POSITIVE)],
        [("Согласование услуги", VkKeyboardColor.PRIMARY), ("Статус заявки", VkKeyboardColor.SECONDARY)],
        [("Администратор", VkKeyboardColor.NEGATIVE), ("Сбросить данные", VkKeyboardColor.SECONDARY)],
    ])


def back_keyboard():
    return _button_rows([
        [("В главное меню", VkKeyboardColor.SECONDARY)],
    ])


def yes_no_keyboard():
    return _button_rows([
        [("Да", VkKeyboardColor.POSITIVE), ("Нет", VkKeyboardColor.NEGATIVE)],
        [("В главное меню", VkKeyboardColor.SECONDARY)],
    ])


def options_keyboard(options, back=True):
    keyboard = VkKeyboard(one_time=False)
    for index, option in enumerate(options):
        if index and index % 2 == 0:
            keyboard.add_line()
        keyboard.add_button(option, color=VkKeyboardColor.PRIMARY)
    if back:
        keyboard.add_line()
        keyboard.add_button("В главное меню", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()
