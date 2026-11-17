"""
БИЗНЕС-ТРЕКЕР на Kivy: версия с дз

добавлено:
1) график расходов по категориям
2) синхронизация с облаком
3) доходы, расходы и баланс

Запуск:  python main_hw.py
"""

import csv
import io
import json
import os
from datetime import datetime

from kivy.app import App
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.network.urlrequest import UrlRequest
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.screenmanager import Screen, ScreenManager

try:
    from matplotlib.figure import Figure
except ImportError:
    Figure = None

try:
    from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
except ImportError:
    try:
        from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
    except ImportError:
        FigureCanvasKivyAgg = None
        
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FIREBASE_URL = 'https://expense-tracker-be6c0-default-rtdb.firebaseio.com'

EXPENSE_CATEGORIES = ['Офис', 'Зарплаты', 'Маркетинг', 'Логистика', 'Налоги', 'Прочее']
INCOME_CATEGORIES = ['Продажи', 'Услуги', 'Инвестиции', 'Прочее']
PLACEHOLDER = 'Выберите категорию'

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
        text: ('+ ' if root.kind == 'income' else '- ') + '{:.2f} руб.'.format(root.amount)
        size_hint_x: 0.3
        color: (0.35, 0.9, 0.35, 1) if root.kind == 'income' else (1, 0.35, 0.35, 1)

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
        padding: dp(15)
        spacing: dp(8)

        Label:
            text: 'БИЗНЕС-ТРЕКЕР'
            font_size: sp(22)
            bold: True
            color: 0.3, 0.55, 1, 1
            size_hint_y: None
            height: dp(40)

        BoxLayout:
            size_hint_y: None
            height: dp(46)
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
                text: 'График'
                on_press: root.show_chart()
                background_color: 0.6, 0.3, 0.6, 1

        BoxLayout:
            size_hint_y: None
            height: dp(46)
            spacing: dp(8)
            Button:
                text: 'Экспорт CSV'
                on_press: root.export_data()
                background_color: 0.7, 0.5, 0.2, 1
            Button:
                text: 'Облако'
                on_press: root.sync_cloud()
                background_color: 0.2, 0.5, 0.7, 1

        BoxLayout:
            size_hint_y: None
            height: dp(60)
            Label:
                text: 'Доходы' + chr(10) + '{:.2f}'.format(root.total_income)
                halign: 'center'
                color: 0.35, 0.9, 0.35, 1
            Label:
                text: 'Расходы' + chr(10) + '{:.2f}'.format(root.total_expenses)
                halign: 'center'
                color: 1, 0.35, 0.35, 1
            Label:
                text: 'Баланс' + chr(10) + '{:.2f}'.format(root.balance)
                halign: 'center'
                bold: True
                color: (0.35, 0.9, 0.35, 1) if root.balance >= 0 else (1, 0.35, 0.35, 1)

        ExpensesRV:
            id: rv

<AddRecordPopup>:
    title: 'Новая операция'
    size_hint: 0.9, None
    height: dp(470)
    auto_dismiss: False
    BoxLayout:
        orientation: 'vertical'
        padding: dp(15)
        spacing: dp(8)

        Label:
            text: 'Тип операции:'
            size_hint_y: None
            height: dp(24)
        Spinner:
            id: type_spinner
            text: 'Расход'
            values: ['Расход', 'Доход']
            size_hint_y: None
            height: dp(44)

        Label:
            text: 'Категория:'
            size_hint_y: None
            height: dp(24)
        Spinner:
            id: category_spinner
            text: 'Выберите категорию'
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
                on_press: root.save_record()
                background_color: 0.2, 0.6, 0.2, 1
"""
Builder.load_string(KV)


# --- Бизнес-логика и модели данных ---
class ExpenseRow(RecycleDataViewBehavior, BoxLayout):
    category = StringProperty('')
    description = StringProperty('')
    amount = NumericProperty(0)
    kind = StringProperty('expense')      
    selected = BooleanProperty(False)
    index = None

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        return super().refresh_view_attrs(rv, index, data)


class ExpensesRV(RecycleView):
    pass


# --- Экран приложения ---
class MainScreen(Screen):
    total_income = NumericProperty(0)
    total_expenses = NumericProperty(0)
    balance = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = JsonStore(os.path.join(BASE_DIR, 'expenses.json'))
        self.load_records()

    # --- данные ---
    def records(self):
        result = []
        for key in self.store.keys():
            r = self.store.get(key)
            result.append({
                'category': r.get('category', ''),
                'description': r.get('description', ''),
                'amount': float(r.get('amount', 0)),
                'kind': r.get('kind', 'expense'),
                'date': r.get('date', ''),
            })
        result.sort(key=lambda r: r['date'], reverse=True)
        return result

    def sum_by_category(self, kind):
        totals = {}
        for r in self.records():
            if r['kind'] == kind:
                totals[r['category']] = totals.get(r['category'], 0) + r['amount']
        return totals

    def load_records(self):
        rows = self.records()
        self.ids.rv.data = [
            {'category': r['category'], 'description': r['description'],
             'amount': r['amount'], 'kind': r['kind']}
            for r in rows
        ]
        self.total_income = sum(r['amount'] for r in rows if r['kind'] == 'income')
        self.total_expenses = sum(r['amount'] for r in rows if r['kind'] == 'expense')
        self.balance = self.total_income - self.total_expenses

    def add_record(self, kind, category, description, amount_text):
        try:
            amount = float(amount_text.replace(',', '.'))
        except ValueError:
            self.show_message('Ошибка', 'Введите корректную сумму')
            return False
        if amount <= 0:
            self.show_message('Ошибка', 'Сумма должна быть больше нуля')
            return False

        now = datetime.now()
        # ВАЖНО: в ключе нет точки, иначе Firebase его не примет
        self.store.put(
            f'rec_{int(now.timestamp() * 1000)}',
            kind=kind, category=category, description=description,
            amount=amount, date=now.strftime('%Y-%m-%d %H:%M:%S'),
        )
        self.load_records()
        return True

    # --- окна ---
    def show_add_popup(self):
        AddRecordPopup(main_screen=self).open()

    def show_message(self, title, message):
        Popup(title=title, content=Label(text=message, halign='center'),
              size_hint=(0.8, 0.35)).open()

    def show_analytics(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=6)
        for title, kind in (('Расходы', 'expense'), ('Доходы', 'income')):
            content.add_widget(Label(text=title, bold=True, font_size='17sp'))
            totals = self.sum_by_category(kind)
            if not totals:
                content.add_widget(Label(text='нет данных'))
            for category, total in sorted(totals.items(), key=lambda kv: -kv[1]):
                content.add_widget(Label(text=f'{category}: {total:.2f} руб.'))
        content.add_widget(Label(text=f'Баланс: {self.balance:.2f} руб.', bold=True))
        Popup(title='Аналитика', content=content, size_hint=(0.85, 0.75)).open()

    # --- график ---
    def show_chart(self):
        totals = self.sum_by_category('expense')
        if not totals:
            self.show_message('График', 'Сначала добавьте хотя бы один расход')
            return
        if Figure is None:
            self.show_message('График', 'Не установлен matplotlib')
            return

        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        names = list(totals.keys())
        ax.bar(names, [totals[n] for n in names], color='tab:red')
        ax.set_title('Расходы по категориям')
        ax.set_ylabel('руб.')
        ax.tick_params(axis='x', labelrotation=30)
        fig.tight_layout()

        if FigureCanvasKivyAgg is not None:
            widget = FigureCanvasKivyAgg(fig)          
        else:
            buf = io.BytesIO()                         
            fig.savefig(buf, format='png')
            buf.seek(0)
            widget = Image(texture=CoreImage(buf, ext='png').texture)

        Popup(title='График расходов', content=widget, size_hint=(0.95, 0.7)).open()

    # --- экспорт ---
    def export_data(self):
        path = os.path.join(BASE_DIR, 'expenses_export.csv')
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['Дата', 'Тип', 'Категория', 'Описание', 'Сумма'])
                for r in reversed(self.records()):
                    kind = 'Доход' if r['kind'] == 'income' else 'Расход'
                    writer.writerow([r['date'], kind, r['category'], r['description'], r['amount']])
            self.show_message('Успех', 'Данные выгружены в файл:\n' + path)
        except OSError as e:
            self.show_message('Ошибка', str(e))

    # --- облако ---
    def sync_cloud(self):
        self._url = FIREBASE_URL.strip().rstrip('/')
        print('CLOUD: кнопка нажата, адрес =', repr(self._url))    

        if not self._url:
            self.show_message('Облако', 'Укажите адрес базы')
            return
        if not self._url.startswith('https://') or 'console.firebase' in self._url:
            self.show_message(
                'Облако',
                'Нужен адрес самой базы, а не страницы консоли.\n'
                'Он оканчивается на firebaseio.com\nили firebasedatabase.app')
            return

        self._wait = Popup(title='Облако', content=Label(text='Подключаюсь...'),
                           size_hint=(0.6, 0.25))
        self._wait.open()
        UrlRequest(
            f'{self._url}/expenses.json',
            on_success=self._cloud_downloaded,
            on_failure=self._cloud_error,
            on_error=self._cloud_error,
            timeout=15,
        )

    def _cloud_done(self, title, message):
        print('CLOUD:', title, '|', message)
        if getattr(self, '_wait', None):
            self._wait.dismiss()
            self._wait = None
        self.show_message(title, message)

    def _cloud_downloaded(self, request, result):
        print('CLOUD: получен ответ', type(result).__name__)
        try:
            added = 0
            if isinstance(result, dict):            
                for key, rec in result.items():
                    if isinstance(rec, dict) and not self.store.exists(key):
                        self.store.put(key, **rec)
                        added += 1
            self.load_records()

            everything = {k: self.store.get(k) for k in self.store.keys()}
            UrlRequest(
                f'{self._url}/expenses.json',
                req_body=json.dumps(everything),
                req_headers={'Content-Type': 'application/json'},
                method='PUT',
                on_success=lambda req, res: self._cloud_done(
                    'Облако', f'Синхронизировано.\nПолучено новых записей: {added}'),
                on_failure=self._cloud_error,
                on_error=self._cloud_error,
                timeout=15,
            )
        except Exception as e:                  
            self._cloud_done('Облако', f'Ошибка обработки ответа:\n{e!r}')

    def _cloud_error(self, request, error):
        text = str(error)
        if len(text) > 200:
            text = text[:200] + '...'
        self._cloud_done('Облако', f'Не удалось связаться с облаком:\n{text}')


# --- Новая операция ---
class AddRecordPopup(Popup):
    def __init__(self, main_screen, **kwargs):
        super().__init__(**kwargs)
        self.main_screen = main_screen
        # при смене типа (Расход/Доход) меняем список категорий
        self.ids.type_spinner.bind(text=lambda *args: self.update_categories())
        self.update_categories()

    def current_kind(self):
        return 'income' if self.ids.type_spinner.text == 'Доход' else 'expense'

    def update_categories(self):
        spinner = self.ids.category_spinner
        spinner.values = INCOME_CATEGORIES if self.current_kind() == 'income' else EXPENSE_CATEGORIES
        spinner.text = PLACEHOLDER

    def save_record(self):
        category = self.ids.category_spinner.text
        description = self.ids.description_input.text.strip()
        amount = self.ids.amount_input.text.strip()

        if category == PLACEHOLDER:
            self.main_screen.show_message('Ошибка', 'Выберите категорию')
            return
        if not description or not amount:
            self.main_screen.show_message('Ошибка', 'Заполните все поля')
            return

        if self.main_screen.add_record(self.current_kind(), category, description, amount):
            self.dismiss()


# --- Основное приложение ---
class ExpenseTrackerApp(App):
    def build(self):
        self.title = 'Business Tracker'
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm

    def on_pause(self):
        return True


# --- Точка входа ---
if __name__ == '__main__':
    ExpenseTrackerApp().run()
