from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'sua_chave_super_secreta'  # troque para uma chave secreta forte

# Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '460860'  # altere para sua senha
app.config['MYSQL_DB'] = 'agendamento'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
mysql = MySQL(app)

# Config Email (exemplo Gmail - use senha de app)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'cclipspnb@gmail.com'         # seu email real
app.config['MAIL_PASSWORD'] = 'axed yhgo btwa flhb'       # senha de app do gmail
mail = Mail(app)

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        senha = request.form['senha']
        tipo = request.form.get('tipo', 'cliente')

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE username = %s OR email = %s", (username, email))
        if cur.fetchone():
            flash("Usuário ou e-mail já cadastrado.", "error")
            return render_template('register.html')

        senha_hash = generate_password_hash(senha)
        cur.execute("INSERT INTO usuarios (username, email, senha, tipo) VALUES (%s, %s, %s, %s)",
                    (username, email, senha_hash, tipo))
        mysql.connection.commit()
        flash("Cadastro realizado com sucesso! Faça login.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        senha = request.form['senha']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        user = cur.fetchone()

        if user and check_password_hash(user['senha'], senha):
            session['usuario_id'] = user['id']
            session['username'] = user['username']
            session['tipo'] = user['tipo']
            flash("Login efetuado com sucesso!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Usuário ou senha inválidos.", "error")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    if session['tipo'] == 'admin':
        cur.execute("""SELECT a.id, u.username, u.email, a.data, a.hora, a.descricao, a.confirmado 
                       FROM agendamentos a JOIN usuarios u ON a.usuario_id = u.id 
                       ORDER BY a.data, a.hora""")
        agendamentos = cur.fetchall()
        return render_template('dashboard_admin.html', agendamentos=agendamentos)
    else:
        cur.execute("SELECT * FROM agendamentos WHERE usuario_id = %s ORDER BY data, hora", (session['usuario_id'],))
        agendamentos = cur.fetchall()
        return render_template('dashboard_cliente.html', agendamentos=agendamentos)
@app.route('/agendar', methods=['GET', 'POST'])
def agendar():
    if session.get('tipo') != 'cliente':
        flash("Somente clientes podem agendar.", "error")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        data_str = request.form['data']
        hora_str = request.form['hora']
        descricao = request.form['descricao'].strip()

        # Validar que data está na semana atual
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
        hoje = datetime.today().date()
        monday = hoje - timedelta(days=hoje.weekday())  # segunda da semana atual
        sunday = monday + timedelta(days=6)

        if data_obj < monday or data_obj > sunday:
            flash("Você só pode agendar dentro da semana atual.", "error")
            return render_template('agendar.html')

        # Validar que não marca horário passado se for hoje
        agora = datetime.now()
        hora_obj = datetime.strptime(hora_str, '%H:%M').time()
        datahora = datetime.combine(data_obj, hora_obj)

        if data_obj == hoje and datahora < agora:
            flash("Não é possível agendar horário já passado no dia atual.", "error")
            return render_template('agendar.html')

        cur = mysql.connection.cursor()
        cur.execute("""SELECT * FROM agendamentos WHERE data = %s AND hora = %s AND confirmado = TRUE""",
                    (data_str, hora_str))
        if cur.fetchone():
            flash("Esse horário já está confirmado para outro cliente.", "error")
        else:
            try:
                cur.execute("INSERT INTO agendamentos (usuario_id, data, hora, descricao) VALUES (%s, %s, %s, %s)",
                            (session['usuario_id'], data_str, hora_str, descricao))
                mysql.connection.commit()
                flash("Agendamento feito! Aguarde confirmação.", "success")
            except:
                flash("Erro: Já existe agendamento pendente nesse horário.", "error")

    return render_template('agendar.html')

@app.route('/confirmar/<int:id>')
def confirmar(id):
    if session.get('tipo') != 'admin':
        flash("Acesso negado.", "error")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""SELECT a.*, u.email, u.username FROM agendamentos a JOIN usuarios u ON a.usuario_id = u.id WHERE a.id = %s""", (id,))
    ag = cur.fetchone()

    if ag:
        cur.execute("UPDATE agendamentos SET confirmado = TRUE WHERE id = %s", (id,))
        mysql.connection.commit()

        try:
            msg = Message(subject="Confirmação de Agendamento",
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[ag['email']])
            msg.body = f"Olá {ag['username']},\n\nSeu agendamento para {ag['data']} às {ag['hora']} foi confirmado.\n\nObrigado!"
            mail.send(msg)
            flash("Agendamento confirmado e e-mail enviado!", "success")
        except Exception as e:
            flash(f"Agendamento confirmado, mas falha ao enviar e-mail: {e}", "error")

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Logout realizado.", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
