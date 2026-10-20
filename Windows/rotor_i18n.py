"""Textos da interface. Chaves e dados persistidos independem do idioma."""
import math
import re
from PIL import Image, ImageDraw

LANGUAGES = {"en": "English", "pt": "Português", "es": "Español",
             "de": "Deutsch", "ru": "Русский"}
ORDER = ("pt", "en", "es", "de", "ru")
# Cada entrada contém português, inglês, espanhol, alemão e russo.
TEXT = {
 "subtitle": ("Controle de azimute · USB", "Azimuth control · USB", "Control de azimut · USB", "Azimutsteuerung · USB", "Управление азимутом · USB"),
 "refresh": ("Atualizar portas", "Refresh ports", "Actualizar puertos", "Ports aktualisieren", "Обновить порты"),
 "connect": ("Conectar", "Connect", "Conectar", "Verbinden", "Подключить"),
 "disconnect": ("Desconectar", "Disconnect", "Desconectar", "Trennen", "Отключить"),
 "disconnected": ("Desconectado", "Disconnected", "Desconectado", "Getrennt", "Отключено"),
 "connecting": ("Conectando…", "Connecting…", "Conectando…", "Verbindung wird hergestellt…", "Подключение…"),
 "connected": ("{port} · Firmware {version} · conectado", "{port} · Firmware {version} · connected", "{port} · Firmware {version} · conectado", "{port} · Firmware {version} · verbunden", "{port} · Прошивка {version} · подключено"),
 "no_ports": ("Nenhuma porta COM encontrada.", "No COM ports found.", "No se encontraron puertos COM.", "Keine COM-Ports gefunden.", "COM-порты не найдены."),
 "current_azimuth": ("AZIMUTE ATUAL", "CURRENT AZIMUTH", "AZIMUT ACTUAL", "AKTUELLER AZIMUT", "ТЕКУЩИЙ АЗИМУТ"),
 "waiting_rotor": ("AGUARDANDO ROTOR", "WAITING FOR ROTOR", "ESPERANDO ROTOR", "WARTE AUF ROTOR", "ОЖИДАНИЕ РОТОРА"),
 "no_telemetry": ("SEM TELEMETRIA", "NO TELEMETRY", "SIN TELEMETRÍA", "KEINE TELEMETRIE", "НЕТ ТЕЛЕМЕТРИИ"),
 "left_limit": ("Limite esquerdo", "Left limit", "Límite izquierdo", "Linker Anschlag", "Левый предел"),
 "right_limit": ("Limite direito", "Right limit", "Límite derecho", "Rechter Anschlag", "Правый предел"),
 "left": ("ESQ", "LEFT", "IZQ", "LINKS", "ВЛЕВО"),
 "stop": ("PARAR", "STOP", "PARAR", "STOPP", "СТОП"),
 "right": ("DIR", "RIGHT", "DER", "RECHTS", "ВПРАВО"),
 "hold_hint": ("Segure para girar · Esc: parar", "Hold to turn · Esc: stop", "Mantenga para girar · Esc: parar", "Halten: drehen · Esc: Stopp", "Удерживать: поворот · Esc: стоп"),
 "max_speed": ("Velocidade máxima", "Maximum speed", "Velocidad máxima", "Höchstgeschwindigkeit", "Максимальная скорость"),
 "speed_value": ("Nível {level} / 6", "Level {level} / 6", "Nivel {level} / 6", "Stufe {level} / 6", "Уровень {level} / 6"),
 "speed_wait": ("Aguardando limite do Arduino", "Waiting for Arduino limit", "Esperando límite del Arduino", "Warte auf Arduino-Limit", "Ожидание лимита Arduino"),
 "speed_saving": ("Salvando no Arduino…", "Saving to Arduino…", "Guardando en Arduino…", "Speichern auf Arduino…", "Сохранение в Arduino…"),
 "speed_saved": ("Limite salvo: nível {level}/6.", "Limit saved: level {level}/6.", "Límite guardado: nivel {level}/6.", "Limit gespeichert: Stufe {level}/6.", "Лимит сохранён: уровень {level}/6."),
 "speed_timeout": ("O Arduino não confirmou o limite. Reconecte para conferir.", "Arduino did not confirm the limit. Reconnect to check.", "Arduino no confirmó el límite. Reconecte para verificar.", "Arduino hat das Limit nicht bestätigt. Zur Prüfung neu verbinden.", "Arduino не подтвердил лимит. Подключитесь заново для проверки."),
 "target_label": ("Novo ângulo (0° a 360°)", "New angle (0° to 360°)", "Nuevo ángulo (0° a 360°)", "Neuer Winkel (0° bis 360°)", "Новый угол (0°–360°)"),
 "active_target": ("Alvo {target:.1f}° · faltam {remaining:.1f}°", "Target {target:.1f}° · {remaining:.1f}° left", "Destino {target:.1f}° · faltan {remaining:.1f}°", "Ziel {target:.1f}° · noch {remaining:.1f}°", "Цель {target:.1f}° · осталось {remaining:.1f}°"),
 "point": ("APONTAR", "POINT", "APUNTAR", "ANFAHREN", "НАВЕСТИ"),
 "grid_label": ("Destino por grid (até 6 caracteres)", "Target grid (up to 6 characters)", "Grid destino (hasta 6 caracteres)", "Ziel-Locator (bis zu 6 Zeichen)", "Локатор цели (до 6 знаков)"),
 "calculate": ("Calcular", "Calculate", "Calcular", "Berechnen", "Расчёт"),
 "clear": ("Limpar", "Clear", "Borrar", "Löschen", "Сброс"),
 "point_grid": ("APONTAR PARA O GRID", "POINT TO GRID", "APUNTAR AL GRID", "LOCATOR ANFAHREN", "НАВЕСТИ НА ЛОКАТОР"),
 "grid_prompt": ("Digite o grid e clique em Calcular.", "Enter a grid and click Calculate.", "Introduzca el grid y pulse Calcular.", "Locator eingeben und Berechnen wählen.", "Введите локатор и нажмите «Расчёт»."),
 "grid_initial": ("Configure a estação e calcule o destino.", "Set the station and calculate the target.", "Configure la estación y calcule el destino.", "Station einstellen und Ziel berechnen.", "Настройте станцию и рассчитайте цель."),
 "grid_result": ("{grid} (centro)\n{azimuth:.1f}° · {distance:.1f} km", "{grid} (centre)\n{azimuth:.1f}° · {distance:.1f} km", "{grid} (centro)\n{azimuth:.1f}° · {distance:.1f} km", "{grid} (Mitte)\n{azimuth:.1f}° · {distance:.1f} km", "{grid} (центр)\n{azimuth:.1f}° · {distance:.1f} км"),
 "simulation": ("SIMULAÇÃO", "SIMULATION", "SIMULACIÓN", "SIMULATION", "СИМУЛЯЦИЯ"),
 "simulation_hint": ("SIMULAÇÃO · sem motor conectado", "SIMULATION · no motor connected", "SIMULACIÓN · sin motor conectado", "SIMULATION · kein Motor angeschlossen", "СИМУЛЯЦИЯ · мотор не подключён"),
 "select_port": ("Selecione a porta COM e conecte.", "Select the COM port and connect.", "Seleccione el puerto COM y conecte.", "COM-Port wählen und verbinden.", "Выберите COM-порт и подключитесь."),
 "verifying": ("Confirmando firmware e posição.", "Checking firmware and position.", "Verificando firmware y posición.", "Firmware und Position werden geprüft.", "Проверка прошивки и положения."),
 "connection_established": ("Conexão estabelecida; comandos habilitados.", "Connected; controls enabled.", "Conexión establecida; controles habilitados.", "Verbunden; Steuerung freigegeben.", "Соединение установлено; управление доступно."),
 "identified": ("Firmware {version} identificado.", "Firmware {version} identified.", "Firmware {version} identificado.", "Firmware {version} erkannt.", "Обнаружена прошивка {version}."),
 "stop_requested": ("Parada solicitada.", "Stop requested.", "Parada solicitada.", "Stopp angefordert.", "Запрошена остановка."),
 "move_requested": ("Apontamento solicitado: {angle:g}°.", "Pointing requested: {angle:g}°.", "Apuntamiento solicitado: {angle:g}°.", "Ziel angefordert: {angle:g}°.", "Запрошено наведение: {angle:g}°."),
 "telemetry_expired": ("Telemetria expirou; parada solicitada.", "Telemetry expired; stop requested.", "Telemetría vencida; parada solicitada.", "Telemetrie abgelaufen; Stopp angefordert.", "Телеметрия просрочена; запрошена остановка."),
 "check_usb": ("Confira o cabo USB e conecte novamente.", "Check the USB cable and reconnect.", "Revise el cable USB y reconecte.", "USB-Kabel prüfen und neu verbinden.", "Проверьте USB-кабель и подключитесь заново."),
 "connection_error": ("Erro de conexão", "Connection error", "Error de conexión", "Verbindungsfehler", "Ошибка подключения"),
 "connection_closed": ("Conexão encerrada", "Connection closed", "Conexión cerrada", "Verbindung beendet", "Соединение закрыто"),
 "mode_0": ("Parado", "Stopped", "Parado", "Gestoppt", "Остановлен"),
 "mode_1": ("Botões físicos", "Local buttons", "Botones físicos", "Lokale Tasten", "Кнопки контроллера"),
 "mode_2": ("Manual pelo computador", "Manual from computer", "Manual desde el PC", "Manuell am PC", "Ручное управление с ПК"),
 "mode_3": ("Apontamento automático", "Automatic pointing", "Apuntamiento automático", "Automatische Positionierung", "Автоматическое наведение"),
 "mode_4": ("Falha · corrija e pressione PARAR", "Fault · correct and press STOP", "Fallo · corrija y pulse PARAR", "Fehler · beheben und STOPP drücken", "Ошибка · устраните и нажмите СТОП"),
 "mode_5": ("Configurando no Arduino", "Arduino settings open", "Configurando en Arduino", "Einstellung am Arduino", "Настройка на Arduino"),
 "reason_0": ("Parada pelo operador", "Stopped by operator", "Parada del operador", "Vom Bediener gestoppt", "Остановлен оператором"),
 "reason_1": ("Alvo atingido", "Target reached", "Destino alcanzado", "Ziel erreicht", "Цель достигнута"),
 "reason_2": ("Limite de curso", "Travel limit", "Límite de recorrido", "Endanschlag", "Предел хода"),
 "reason_3": ("Comunicação interrompida", "Communication lost", "Comunicación interrumpida", "Kommunikation unterbrochen", "Связь потеряна"),
 "reason_4": ("Leitura do sensor inválida", "Invalid sensor reading", "Lectura de sensor no válida", "Ungültiger Sensorwert", "Недопустимое показание датчика"),
 "reason_5": ("Sem mudança de posição por 8 s", "No position change for 8 s", "Sin cambio de posición por 8 s", "Seit 8 s keine Positionsänderung", "Положение не меняется 8 с"),
 "reason_6": ("Tempo de movimento excedido", "Movement timeout", "Tiempo de movimiento excedido", "Bewegungszeit überschritten", "Превышено время движения"),
 "reason_7": ("Controle pelos botões físicos", "Controlled by local buttons", "Control mediante botones físicos", "Steuerung über lokale Tasten", "Управление кнопками контроллера"),
 "reason_8": ("Dois botões físicos pressionados", "Both local buttons pressed", "Ambos botones físicos pulsados", "Beide lokalen Tasten gedrückt", "Нажаты обе кнопки контроллера"),
 "reason_9": ("Ajuste de velocidade no Arduino", "Speed adjustment on Arduino", "Ajuste de velocidad en Arduino", "Geschwindigkeit am Arduino einstellen", "Настройка скорости на Arduino"),
 "err_LOCAL": ("Solte os botões físicos para usar o PC.", "Release the local buttons to use the PC.", "Suelte los botones físicos para usar el PC.", "Lokale Tasten loslassen, um den PC zu nutzen.", "Отпустите кнопки контроллера для управления с ПК."),
 "err_FAULT": ("Corrija a falha e pressione PARAR.", "Correct the fault and press STOP.", "Corrija el fallo y pulse PARAR.", "Fehler beheben und STOPP drücken.", "Устраните ошибку и нажмите СТОП."),
 "err_ANGLE": ("Informe um ângulo de 0° a 360°.", "Enter an angle from 0° to 360°.", "Introduzca un ángulo de 0° a 360°.", "Winkel von 0° bis 360° eingeben.", "Введите угол от 0° до 360°."),
 "err_SPEED": ("Escolha um nível de velocidade de 1 a 6.", "Choose a speed level from 1 to 6.", "Elija un nivel de velocidad de 1 a 6.", "Geschwindigkeitsstufe von 1 bis 6 wählen.", "Выберите уровень скорости от 1 до 6."),
 "err_CONFIG": ("Conclua a configuração pelos botões do Arduino.", "Finish settings using the Arduino buttons.", "Termine la configuración con los botones del Arduino.", "Einstellung mit den Arduino-Tasten abschließen.", "Завершите настройку кнопками Arduino."),
 "err_COMMAND": ("Comando não reconhecido pelo firmware.", "Command not recognised by firmware.", "Comando no reconocido por el firmware.", "Firmware erkennt den Befehl nicht.", "Прошивка не распознала команду."),
 "err_LINE": ("Uma linha serial inválida foi descartada.", "An invalid serial line was discarded.", "Se descartó una línea serie no válida.", "Ungültige serielle Zeile verworfen.", "Отброшена недопустимая строка последовательного порта."),
 "course_available": ("Curso disponível", "Travel available", "Recorrido disponible", "Freier Stellbereich", "Ход доступен"),
 "detail": ("{detail}\n{limit} · PWM {pwm}/255", "{detail}\n{limit} · PWM {pwm}/255", "{detail}\n{limit} · PWM {pwm}/255", "{detail}\n{limit} · PWM {pwm}/255", "{detail}\n{limit} · ШИМ {pwm}/255"),
 "settings_save_error": ("Não foi possível salvar as configurações.", "Could not save settings.", "No se pudo guardar la configuración.", "Einstellungen konnten nicht gespeichert werden.", "Не удалось сохранить настройки."),
 "map_title": ("MAPA DE APONTAMENTO", "POINTING MAP", "MAPA DE APUNTAMIENTO", "RICHTUNGSKARTE", "КАРТА НАВЕДЕНИЯ"),
 "station_settings": ("Configurar estação", "Station settings", "Configurar estación", "Station einstellen", "Настройка станции"),
 "station_title": ("CONFIGURAÇÃO DA ESTAÇÃO", "STATION SETTINGS", "CONFIGURACIÓN DE ESTACIÓN", "STATIONSEINSTELLUNGEN", "НАСТРОЙКА СТАНЦИИ"),
 "station_name": ("Nome / indicativo", "Name / callsign", "Nombre / indicativo", "Name / Rufzeichen", "Имя / позывной"),
 "coords_mode": ("Coordenadas WGS84 em graus decimais", "WGS84 coordinates in decimal degrees", "Coordenadas WGS84 en grados decimales", "WGS84-Koordinaten in Dezimalgrad", "Координаты WGS84 в десятичных градусах"),
 "grid_mode": ("Grid locator (centro da célula)", "Grid locator (cell centre)", "Grid locator (centro de celda)", "Maidenhead-Locator (Zellenmitte)", "Локатор Maidenhead (центр ячейки)"),
 "latitude": ("Latitude (Sul negativo)", "Latitude (south negative)", "Latitud (sur negativo)", "Breitengrad (Süd negativ)", "Широта (юг — отрицательная)"),
 "longitude": ("Longitude (Oeste negativo)", "Longitude (west negative)", "Longitud (oeste negativo)", "Längengrad (West negativ)", "Долгота (запад — отрицательная)"),
 "station_grid": ("Grid de até 6 caracteres — exemplo GG66dr", "Grid up to 6 characters — e.g. GG66dr", "Grid de hasta 6 caracteres — ej. GG66dr", "Locator mit bis zu 6 Zeichen — z. B. GG66dr", "Локатор до 6 знаков — например GG66dr"),
 "latitude_hint": ("O mapa aceita latitudes entre −85° e +85°.", "The map supports latitudes from −85° to +85°.", "El mapa admite latitudes entre −85° y +85°.", "Die Karte unterstützt Breitengrade von −85° bis +85°.", "Карта поддерживает широты от −85° до +85°."),
 "beam_label": ("Abertura total do feixe −3 dB (°)", "Total −3 dB beamwidth (°)", "Apertura total del haz −3 dB (°)", "Gesamte −3-dB-Strahlbreite (°)", "Полная ширина луча −3 дБ (°)"),
 "beam_hint": ("Exemplo: 60° corresponde a 30° para cada lado do centro.", "Example: 60° means 30° on each side of the centre.", "Ejemplo: 60° son 30° a cada lado del centro.", "Beispiel: 60° bedeutet 30° auf jeder Seite der Mitte.", "Пример: 60° — это по 30° с каждой стороны оси."),
 "apply_station": ("Aplicar configuração", "Apply settings", "Aplicar configuración", "Einstellungen übernehmen", "Применить настройки"),
 "cancel": ("Cancelar", "Cancel", "Cancelar", "Abbrechen", "Отмена"),
 "back_map": ("Voltar ao mapa", "Back to map", "Volver al mapa", "Zurück zur Karte", "Назад к карте"),
 "station_needed": ("Configure a localização da estação.", "Set the station location.", "Configure la ubicación de la estación.", "Standort der Station einstellen.", "Задайте местоположение станции."),
 "station_prompt": ("Configure a estação para centralizar o mapa.", "Set the station to centre the map.", "Configure la estación para centrar el mapa.", "Station einstellen, um die Karte zu zentrieren.", "Настройте станцию для центрирования карты."),
 "radius": ("Raio (km)", "Radius (km)", "Radio (km)", "Radius (km)", "Радиус (км)"),
 "apply": ("Aplicar", "Apply", "Aplicar", "Anwenden", "Применить"),
 "opacity": ("Opacidade: {value:.0f}%", "Opacity: {value:.0f}%", "Opacidad: {value:.0f}%", "Deckkraft: {value:.0f}%", "Непрозрачность: {value:.0f}%"),
 "map_wait": ("Aguardando leitura do rotor.", "Waiting for rotor readings.", "Esperando lectura del rotor.", "Warte auf Rotorwerte.", "Ожидание данных ротора."),
 "map_heading": ("Antena: {angle:.1f}°", "Antenna: {angle:.1f}°", "Antena: {angle:.1f}°", "Antenne: {angle:.1f}°", "Антенна: {angle:.1f}°"),
 "cone_hidden": ("Aguardando telemetria · cone oculto", "Waiting for telemetry · beam hidden", "Esperando telemetría · haz oculto", "Warte auf Telemetrie · Strahl ausgeblendet", "Ожидание телеметрии · луч скрыт"),
 "map_state": ("{heading} · feixe {opening:g}° · raio {radius:g} km", "{heading} · beam {opening:g}° · radius {radius:g} km", "{heading} · haz {opening:g}° · radio {radius:g} km", "{heading} · Strahl {opening:g}° · Radius {radius:g} km", "{heading} · луч {opening:g}° · радиус {radius:g} км"),
 "loading_map": ("Carregando mapa…", "Loading map…", "Cargando mapa…", "Karte wird geladen…", "Загрузка карты…"),
 "map_unavailable": ("Mapa indisponível; verifique a internet.", "Map unavailable; check the internet connection.", "Mapa no disponible; revise Internet.", "Karte nicht verfügbar; Internetverbindung prüfen.", "Карта недоступна; проверьте интернет."),
 "map_offline": ("Sem rede: exibindo o mapa disponível em cache.", "Offline: showing the cached map.", "Sin conexión: mostrando el mapa en caché.", "Offline: gespeicherte Karte wird angezeigt.", "Нет сети: показана карта из кэша."),
 "map_no_station": ("Configure a localização da estação\npara abrir o mapa.", "Set the station location\nto open the map.", "Configure la ubicación de la estación\npara abrir el mapa.", "Standort der Station einstellen,\num die Karte zu öffnen.", "Задайте местоположение станции,\nчтобы открыть карту."),
 "map_target": ("Destino {grid} · {bearing:.1f}° · {distance:.1f} km", "Target {grid} · {bearing:.1f}° · {distance:.1f} km", "Destino {grid} · {bearing:.1f}° · {distance:.1f} km", "Ziel {grid} · {bearing:.1f}° · {distance:.1f} km", "Цель {grid} · {bearing:.1f}° · {distance:.1f} км"),
 "invalid_grid": ("Grid inválido. Use 2, 4 ou 6 caracteres, como GG66 ou GG66dr.", "Invalid grid. Use 2, 4 or 6 characters, such as GG66 or GG66dr.", "Grid no válido. Use 2, 4 o 6 caracteres, como GG66 o GG66dr.", "Ungültiger Locator. 2, 4 oder 6 Zeichen verwenden, z. B. GG66 oder GG66dr.", "Недопустимый локатор. Используйте 2, 4 или 6 знаков: GG66 или GG66dr."),
 "same_destination": ("Destino coincide com a estação; escolha outro grid.", "Target matches the station; choose a different grid.", "El destino coincide con la estación; elija otro grid.", "Ziel entspricht der Station; anderen Locator wählen.", "Цель совпадает со станцией; выберите другой локатор."),
 "invalid_number": ("{field}: informe um número de {low} a {high}.", "{field}: enter a number from {low} to {high}.", "{field}: introduzca un número de {low} a {high}.", "{field}: Zahl von {low} bis {high} eingeben.", "{field}: введите число от {low} до {high}."),
 "serial_missing": ("pySerial ausente. Execute INSTALAR.bat.", "pySerial is missing. Run INSTALAR.bat.", "Falta pySerial. Ejecute INSTALAR.bat.", "pySerial fehlt. INSTALAR.bat ausführen.", "Нет pySerial. Запустите INSTALAR.bat."),
 "serial_partial": ("Escrita serial incompleta.", "Incomplete serial write.", "Escritura serie incompleta.", "Unvollständige serielle Übertragung.", "Неполная запись в последовательный порт."),
 "firmware_timeout": ("O rotor não respondeu com firmware 1.2. Confira a COM e grave o novo .ino.", "Rotor did not respond with firmware 1.2. Check the COM port and upload the new .ino.", "El rotor no respondió con firmware 1.2. Revise el puerto COM y cargue el nuevo .ino.", "Rotor antwortet nicht mit Firmware 1.2. COM-Port prüfen und neue .ino-Datei übertragen.", "Ротор не ответил прошивкой 1.2. Проверьте COM-порт и загрузите новый файл .ino."),
 "telemetry_missing": ("Sem telemetria. Confira o USB e a alimentação.", "No telemetry. Check USB and power.", "Sin telemetría. Revise USB y alimentación.", "Keine Telemetrie. USB und Stromversorgung prüfen.", "Нет телеметрии. Проверьте USB и питание."),
 "board_reset": ("Arduino reiniciou durante a conexão. Conecte novamente.", "Arduino restarted during the connection. Reconnect.", "Arduino se reinició durante la conexión. Reconecte.", "Arduino wurde während der Verbindung neu gestartet. Neu verbinden.", "Arduino перезапустился во время соединения. Подключитесь заново."),
 "firmware_incompatible": ("Firmware incompatível. Grave o firmware 1.2 deste pacote.", "Incompatible firmware. Upload firmware 1.2 from this package.", "Firmware incompatible. Cargue el firmware 1.2 de este paquete.", "Inkompatible Firmware. Firmware 1.2 aus diesem Paket übertragen.", "Несовместимая прошивка. Загрузите прошивку 1.2 из этого пакета."),
 "port_hint": ("Conecte o Arduino e atualize a lista de portas.", "Connect Arduino and refresh the port list.", "Conecte Arduino y actualice los puertos.", "Arduino anschließen und Portliste aktualisieren.", "Подключите Arduino и обновите список портов."),
 "app_install_hint": ("Execute INSTALAR.bat para instalar o pySerial.", "Run INSTALAR.bat to install pySerial.", "Ejecute INSTALAR.bat para instalar pySerial.", "INSTALAR.bat ausführen, um pySerial zu installieren.", "Запустите INSTALAR.bat для установки pySerial."),
 "settings_error": ("Confira os campos indicados abaixo.", "Check the fields below.", "Revise los campos de abajo.", "Bitte die folgenden Felder prüfen.", "Проверьте поля ниже."),
}


class Translator:
    def __init__(self, language="pt"):
        self.language = language if language in LANGUAGES else "pt"

    def __call__(self, key, **values):
        row = TEXT.get(key)
        template = row[ORDER.index(self.language)] if row else str(key)
        return template.format(**values)

    def error(self, error):
        text = str(error)
        if text.startswith("Grid inválido."):
            return self("invalid_grid")
        if text.startswith("Destino coincide"):
            return self("same_destination")
        number = re.fullmatch(r"(.+): informe um número de (.+) a (.+)\.", text)
        if number:
            field, low, high = number.groups()
            key = {"Latitude do mapa": "latitude", "Longitude": "longitude",
                   "Raio": "radius", "Abertura do feixe": "beam_label"}.get(field)
            return self("invalid_number", field=self(key) if key else field, low=low, high=high)
        return self(text)


def flag_image(language, width=24, height=16):
    """Bandeiras desenhadas como ativos da interface, sem depender de emoji."""
    scale = 4
    w, h = width*scale, height*scale
    image = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(image)
    if language in ("de", "ru"):
        colors = ("#111111", "#d31328", "#ffce00") if language == "de" else ("white", "#17469e", "#d52b1e")
        for i, color in enumerate(colors):
            d.rectangle((0, round(h*i/3), w, round(h*(i+1)/3)), fill=color)
    elif language == "es":
        d.rectangle((0, 0, w, h), fill="#aa151b")
        d.rectangle((0, h//4, w, 3*h//4), fill="#f1bf00")
        d.rectangle((w//4-5, h//2-7, w//4+5, h//2+8), fill="#aa151b")
        d.rectangle((w//4-7, h//2-9, w//4+7, h//2-6), fill="#c9981d")
    elif language == "pt":
        d.rectangle((0, 0, w, h), fill="#009b3a")
        d.polygon([(w//2, 5), (w-7, h//2), (w//2, h-5), (7, h//2)], fill="#ffdf00")
        r = h*.26
        d.ellipse((w/2-r, h/2-r, w/2+r, h/2+r), fill="#002776")
        d.arc((w/2-r-4, h/2-r+7, w/2+r+4, h/2+r+4), 195, 340, fill="white", width=3)
        for x, y in ((.47,.55),(.56,.58),(.48,.64),(.55,.45)):
            d.ellipse((w*x-1,h*y-1,w*x+1,h*y+1),fill="white")
    else:
        for i in range(13):
            d.rectangle((0, round(h*i/13), w, round(h*(i+1)/13)), fill="#b22234" if i%2 == 0 else "white")
        d.rectangle((0, 0, int(w*.42), int(h*7/13)), fill="#3c3b6e")
        for row in range(5):
            for col in range(6):
                x=(col+.5)*w*.42/6; y=(row+.5)*h*7/13/5
                d.ellipse((x-1,y-1,x+1,y+1),fill="white")
    return image.resize((width,height), Image.Resampling.LANCZOS)
