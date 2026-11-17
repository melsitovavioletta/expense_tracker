"""
БИЗНЕС-ТРЕКЕР РАСХОДОВ на Kivy

Запуск:   python main.py
"""

import csv
import os
from datetime import datetime

from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.screenmanager import Screen, ScreenManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

Window.size = (400, 700)

KV = """
<ExpenseRow>:
    canvas.before:
        Color:
            rgba: (0.25, 0.25, 0.25, 1) if self.selected else (0.13, 0.13, 0.13, 1)
        Rectangle:
            pos: self.pos
            size: self.size
    orientation: 'horizontal'
    padding: dp(10)
    size_hint_y: None
    height: dp(60)
    Label:
        text: root.category
        size_hint_x: 0.3
    Label:
        text: root.description
        size_hint_x: 0.4
    Label:
        text: '{:.2f} руб.'.format(root.amount)
        size_hint_x: 0.3
        color: (1, 0.35, 0.35, 1)

<ExpensesRV>:
    viewclass: 'ExpenseRow'
    RecycleBoxLayout:
        default_size: None, dp(60)
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
        orientation: 'vertical'
        spacing: dp(2)

<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(10)

        Label:
            text: 'БИЗНЕС-ТРЕКЕР РАСХОДОВ'
            font_size: sp(22)
            bold: True
            color: 0.3, 0.55, 1, 1
            size_hint_y: None
            height: dp(50)

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: dp(50)
            spacing: dp(8)
            Button:
                text: 'Добавить'
                on_press: root.show_add_popup()
                background_color: 0.2, 0.6, 0.2, 1
            Button:
                text: 'Аналитика'
                on_press: root.show_analytics()
                background_color: 0.3, 0.3, 0.7, 1
            Button:
                text: 'Экспорт'
                on_press: root.export_data()
                background_color: 0.7, 0.5, 0.2, 1

        Label:
            text: 'Общий расход: {:.2f} руб.'.format(root.total_expenses)
            font_size: sp(18)
            bold: True
            color: 1, 0.35, 0.35, 1
            size_hint_y: None
            height: dp(40)

        ExpensesRV:
            id: rv

<AddExpensePopup>:
    title: 'Добавить новый расход'
    size_hint: 0.9, None
    height: dp(400)
    auto_dismiss: False
    BoxLayout:
        orientation: 'vertical'
        padding: dp(15)
        spacing: dp(8)

        Label:
            text: 'Категория:'
            size_hint_y: None
            height: dp(24)
        Spinner:
            id: category_spinner
            text: 'Выберите категорию'
            values: ['Офис', 'Зарплаты', 'Маркетинг', 'Логистика', 'Налоги', 'Прочее']
            size_hint_y: None
            height: dp(44)

        Label:
            text: 'Описание:'
            size_hint_y: None
            height: dp(24)
        TextInput:
            id: description_input
            multiline: False
            size_hint_y: None
            height: dp(44)

        Label:
            text: 'Сумма (руб.):'
            size_hint_y: None
            height: dp(24)
        TextInput:
            id: amount_input
            multiline: False
            input_filter: 'float'
            size_hint_y: None
            height: dp(44)

        BoxLayout:
            spacing: dp(10)
            size_hint_y: None
            height: dp(50)
            Button:
                text: 'Отмена'
                on_press: root.dismiss()
                background_color: 0.8, 0.2, 0.2, 1
            Button:
                text: 'Сохранить'
                on_press: root.save_expense()
                background_color: 0.2, 0.6, 0.2, 1
"""
Builder.load_string(KV)


# --- Бизнес-логика и модели данных ---
class ExpenseRow(RecycleDataViewBehavior, BoxLayout):
    """Одна строка списка. Свойства заполняются из словарей в rv.data."""
    category = StringProperty('')
    description = StringProperty('')
    amount = NumericProperty(0)
    selected = BooleanProperty(False)   # в лекции его не было, а KV его использует
    index = None

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        return super().refresh_view_attrs(rv, index, data)

class ExpensesRV(RecycleView):
    """Сам список. Внешний вид задан в KV (<ExpensesRV>)."""


# --- Экран приложения ---
class MainScreen(Screen):
    total_expenses = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # JsonStore сам читает и пишет expenses.json
        self.store = JsonStore(os.path.join(BASE_DIR, 'expenses.json'))
        self.load_expenses()

    # --- данные ---
    def records(self):
        """Все записи из файла, новые сверху."""
        result = []
        for key in self.store.keys():
            r = self.store.get(key)
            result.append({
                'category': r.get('category', ''),
                'description': r.get('description', ''),
                'amount': float(r.get('amount', 0)),
                'date': r.get('date', ''),
            })
        result.sort(key=lambda r: r['date'], reverse=True)
        return result

    def load_expenses(self):
        """Читает файл, обновляет список и сумму."""
        rows = self.records()
        self.ids.rv.data = [
            {'category': r['category'], 'description': r['description'], 'amount': r['amount']}
            for r in rows
        ]
        self.total_expenses = sum(r['amount'] for r in rows)

    def add_expense(self, category, description, amount_text):
        """Бизнес-логика добавления. Возвращает True, если запись сохранена."""
        try:
            amount = float(amount_text.replace(',', '.'))
        except ValueError:
            self.show_message('Ошибка', 'Введите корректную сумму')
            return False
        if amount <= 0:
            self.show_message('Ошибка', 'Сумма должна быть больше нуля')
            return False

        now = datetime.now()
        self.store.put(
            f'expense_{int(now.timestamp() * 1000)}',
            category=category,
            description=description,
            amount=amount,
            date=now.strftime('%Y-%m-%d %H:%M:%S'),
        )
        self.load_expenses()
        return True

    # --- окна ---
    def show_add_popup(self):
        AddExpensePopup(main_screen=self).open()

    def show_message(self, title, message):
        Popup(
            title=title,
            content=Label(text=message, halign='center'),
            size_hint=(0.8, 0.35),
        ).open()

    def show_analytics(self):
        totals = {}
        for r in self.records():
            totals[r['category']] = totals.get(r['category'], 0) + r['amount']

        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        if not totals:
            content.add_widget(Label(text='Пока нет данных'))
        for category, total in sorted(totals.items(), key=lambda kv: -kv[1]):
            content.add_widget(Label(text=f'{category}: {total:.2f} руб.', font_size='16sp'))
        Popup(title='Аналитика расходов по категориям', content=content,
              size_hint=(0.85, 0.6)).open()

    def export_data(self):
        """Выгрузка в CSV"""
        path = os.path.join(BASE_DIR, 'expenses_export.csv')
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['Дата', 'Категория', 'Описание', 'Сумма'])
                for r in reversed(self.records()):
                    writer.writerow([r['date'], r['category'], r['description'], r['amount']])
            self.show_message('Успех', 'Данные выгружены в файл:\n' + path)
        except OSError as e:
            self.show_message('Ошибка', str(e))

class AddExpensePopup(Popup):
    def __init__(self, main_screen, **kwargs):
        super().__init__(**kwargs)
        self.main_screen = main_screen

    def save_expense(self):
        category = self.ids.category_spinner.text
        description = self.ids.description_input.text.strip()
        amount = self.ids.amount_input.text.strip()

        if category == 'Выберите категорию':
            self.main_screen.show_message('Ошибка', 'Выберите категорию')
            return
        if not description or not amount:
            self.main_screen.show_message('Ошибка', 'Заполните все поля')
            return

        if self.main_screen.add_expense(category, description, amount):
            self.dismiss()


# --- Основное приложение ---
class ExpenseTrackerApp(App):
    def build(self):
        self.title = 'Business Expense Tracker'
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm

    def on_pause(self):
        return True

    def on_resume(self):
        pass


# --- Точка входа ---
if __name__ == '__main__':
    ExpenseTrackerApp().run()
