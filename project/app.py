from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask import send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clined-spa-2024-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clined.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    data_nascimento = db.Column(db.Date)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    observacoes = db.Column(db.Text)

class Servico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    preco = db.Column(db.Float, nullable=False)
    duracao = db.Column(db.Integer, nullable=False)  # em minutos
    ativo = db.Column(db.Boolean, default=True)

class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='agendado')  # agendado, concluido, cancelado
    observacoes = db.Column(db.Text)
    valor = db.Column(db.Float, nullable=False)
    
    cliente = db.relationship('Cliente', backref='agendamentos')
    servico = db.relationship('Servico', backref='agendamentos')

# Routes
@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Login simples (admin/admin123)
        if username == 'admin' and password == 'admin123':
            session['logged_in'] = True
            session['username'] = username
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha incorretos!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    # Estatísticas
    total_clientes = Cliente.query.count()
    total_servicos = Servico.query.filter_by(ativo=True).count()
    
    # Agendamentos de hoje
    hoje = date.today()
    agendamentos_hoje = Agendamento.query.filter(
        db.func.date(Agendamento.data_hora) == hoje,
        Agendamento.status != 'cancelado'
    ).count()
    
    # Receita do mês atual
    primeiro_dia_mes = date.today().replace(day=1)
    receita_mes = db.session.query(db.func.sum(Agendamento.valor)).filter(
        Agendamento.data_hora >= primeiro_dia_mes,
        Agendamento.status == 'concluido'
    ).scalar() or 0
    
    # Próximos agendamentos
    proximos_agendamentos = Agendamento.query.filter(
        Agendamento.data_hora >= datetime.now(),
        Agendamento.status == 'agendado'
    ).order_by(Agendamento.data_hora).limit(5).all()
    
    return render_template('dashboard.html',
                         total_clientes=total_clientes,
                         total_servicos=total_servicos,
                         agendamentos_hoje=agendamentos_hoje,
                         receita_mes=receita_mes,
                         proximos_agendamentos=proximos_agendamentos)

@app.route('/clientes')
def clientes():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    search = request.args.get('search', '')
    
    if search:
        clientes = Cliente.query.filter(
            db.or_(
                Cliente.nome.contains(search),
                Cliente.telefone.contains(search)
            )
        ).order_by(Cliente.nome).all()
    else:
        clientes = Cliente.query.order_by(Cliente.nome).all()
    
    return render_template('clientes.html', clientes=clientes, search=search)

@app.route('/cliente/novo', methods=['GET', 'POST'])
def novo_cliente():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        nome = request.form['nome']
        telefone = request.form['telefone']
        email = request.form['email']
        data_nascimento = datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date() if request.form['data_nascimento'] else None
        observacoes = request.form['observacoes']
        
        cliente = Cliente(
            nome=nome,
            telefone=telefone,
            email=email,
            data_nascimento=data_nascimento,
            observacoes=observacoes
        )
        
        db.session.add(cliente)
        db.session.commit()
        
        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes'))
    
    return render_template('cliente_form.html')

@app.route('/cliente/<int:id>/editar', methods=['GET', 'POST'])
def editar_cliente(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    cliente = Cliente.query.get_or_404(id)
    
    if request.method == 'POST':
        cliente.nome = request.form['nome']
        cliente.telefone = request.form['telefone']
        cliente.email = request.form['email']
        cliente.data_nascimento = datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date() if request.form['data_nascimento'] else None
        cliente.observacoes = request.form['observacoes']
        
        db.session.commit()
        flash('Cliente atualizado com sucesso!', 'success')
        return redirect(url_for('clientes'))
    
    return render_template('cliente_form.html', cliente=cliente)

@app.route('/servicos')
def servicos():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    servicos = Servico.query.filter_by(ativo=True).order_by(Servico.nome).all()
    return render_template('servicos.html', servicos=servicos)

@app.route('/servico/novo', methods=['GET', 'POST'])
def novo_servico():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        nome = request.form['nome']
        descricao = request.form['descricao']
        preco = float(request.form['preco'])
        duracao = int(request.form['duracao'])
        
        servico = Servico(
            nome=nome,
            descricao=descricao,
            preco=preco,
            duracao=duracao
        )
        
        db.session.add(servico)
        db.session.commit()
        
        flash('Serviço cadastrado com sucesso!', 'success')
        return redirect(url_for('servicos'))
    
    return render_template('servico_form.html')

@app.route('/agendamentos')
def agendamentos():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    agendamentos = Agendamento.query.order_by(Agendamento.data_hora.desc()).all()
    return render_template('agendamentos.html', agendamentos=agendamentos)

@app.route('/agendamento/novo', methods=['GET', 'POST'])
def novo_agendamento():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        cliente_id = int(request.form['cliente_id'])
        servico_id = int(request.form['servico_id'])
        data_hora = datetime.strptime(request.form['data_hora'], '%Y-%m-%dT%H:%M')
        observacoes = request.form['observacoes']
        
        servico = Servico.query.get(servico_id)
        
        agendamento = Agendamento(
            cliente_id=cliente_id,
            servico_id=servico_id,
            data_hora=data_hora,
            observacoes=observacoes,
            valor=servico.preco
        )
        
        db.session.add(agendamento)
        db.session.commit()
        
        flash('Agendamento criado com sucesso!', 'success')
        return redirect(url_for('agendamentos'))
    
    search_cliente = request.args.get('search_cliente', '')
    
    if search_cliente:
        clientes = Cliente.query.filter(
            db.or_(
                Cliente.nome.contains(search_cliente),
                Cliente.telefone.contains(search_cliente)
            )
        ).order_by(Cliente.nome).all()
    else:
        clientes = Cliente.query.order_by(Cliente.nome).all()
        
    servicos = Servico.query.filter_by(ativo=True).order_by(Servico.nome).all()
    
    return render_template('agendamento_form.html', clientes=clientes, servicos=servicos, search_cliente=search_cliente)

@app.route('/agendamento/<int:id>/status/<status>')
def atualizar_status_agendamento(id, status):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    agendamento = Agendamento.query.get_or_404(id)
    agendamento.status = status
    
    db.session.commit()
    
    flash(f'Agendamento marcado como {status}!', 'success')
    return redirect(url_for('agendamentos'))



@app.route('/relatorios')
def relatorios():
    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    return render_template('relatorios.html', hoje=hoje, ontem=ontem)



@app.route('/relatorios/pdf')
def gerar_relatorio_pdf():
    # Exemplo simples: PDF em memória
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph("Relatório de Agendamentos", styles['Title']))

    # Exemplo: lista de agendamentos
    agendamentos = Agendamento.query.order_by(Agendamento.data_hora.desc()).all()
    data = [["Cliente", "Serviço", "Data/Hora", "Status", "Valor"]]
    for a in agendamentos:
        data.append([
            a.cliente.nome,
            a.servico.nome,
            a.data_hora.strftime('%d/%m/%Y %H:%M'),
            a.status,
            f"R$ {a.valor:.2f}"
        ])

    t = Table(data, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ]))
    elements.append(t)

    doc.build(elements)
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name="relatorio.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Criar serviços padrão se não existirem
        if Servico.query.count() == 0:
            servicos_padrao = [
                Servico(nome='Massagem Relaxante', descricao='Massagem para relaxamento corporal', preco=80.0, duracao=60),
                Servico(nome='Limpeza de Pele', descricao='Limpeza facial profunda', preco=60.0, duracao=90),
                Servico(nome='Manicure e Pedicure', descricao='Cuidados para unhas das mãos e pés', preco=35.0, duracao=60),
                Servico(nome='Massagem Modeladora', descricao='Massagem para modelar o corpo', preco=90.0, duracao=60),
                Servico(nome='Hidratação Facial', descricao='Tratamento hidratante para o rosto', preco=50.0, duracao=45)
            ]
            
            for servico in servicos_padrao:
                db.session.add(servico)
            
            db.session.commit()
    
    app.run(debug=True)