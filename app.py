import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'  # Necessária para mensagens flash

# Configuração para upload da logo
UPLOAD_FOLDER = 'static'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ---------- Funções auxiliares ----------
def conectar_banco():
    conn = sqlite3.connect('registros.db')
    conn.row_factory = sqlite3.Row  # Permite acesso por nome da coluna
    return conn

def criar_tabela():
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            setor TEXT NOT NULL,
            log TEXT NOT NULL,
            id_campo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            motivo TEXT NOT NULL,
            observacao TEXT
        )
    ''')
    conn.commit()
    conn.close()

criar_tabela()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- Rotas ----------
@app.route('/')
def index():
    return redirect(url_for('cadastro'))

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        # Coleta dados do formulário
        data = request.form['data']
        setor = request.form['setor']
        log = request.form['log']
        id_campo = request.form['id_campo']
        tipo = request.form['tipo']
        motivo = request.form['motivo']
        observacao = request.form.get('observacao', '')

        # Validação simples
        if not all([data, setor, log, id_campo, tipo, motivo]):
            flash('Todos os campos (exceto Observação) são obrigatórios.', 'erro')
            return redirect(url_for('cadastro'))

        # Converte data de DD/MM/AAAA para AAAA-MM-DD
        try:
            data_obj = datetime.strptime(data, '%Y-%m-%d')  # O input date envia AAAA-MM-DD
        except:
            flash('Data inválida.', 'erro')
            return redirect(url_for('cadastro'))

        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO registros (data, setor, log, id_campo, tipo, motivo, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data, setor, log, id_campo, tipo, motivo, observacao))
        conn.commit()
        conn.close()

        flash('Registro salvo com sucesso!', 'sucesso')
        return redirect(url_for('cadastro'))

    # GET: exibe o formulário
    return render_template('cadastro.html')

@app.route('/busca')
def busca():
    return render_template('busca.html')

@app.route('/api/registros')
def api_registros():
    termo = request.args.get('termo', '')
    conn = conectar_banco()
    cur = conn.cursor()
    if termo:
        cur.execute('''
            SELECT * FROM registros
            WHERE data LIKE ? OR setor LIKE ? OR log LIKE ? OR id_campo LIKE ?
               OR tipo LIKE ? OR motivo LIKE ? OR observacao LIKE ?
            ORDER BY data DESC
        ''', (f'%{termo}%',)*7)
    else:
        cur.execute('SELECT * FROM registros ORDER BY data DESC')
    registros = cur.fetchall()
    conn.close()

    # Converte para lista de dicionários
    lista = []
    for reg in registros:
        lista.append({
            'id': reg['id'],
            'data': reg['data'],
            'setor': reg['setor'],
            'log': reg['log'],
            'id_campo': reg['id_campo'],
            'tipo': reg['tipo'],
            'motivo': reg['motivo'],
            'observacao': reg['observacao'] if reg['observacao'] else ''
        })
    return jsonify(lista)

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if request.method == 'POST':
        data = request.form['data']
        setor = request.form['setor']
        log = request.form['log']
        id_campo = request.form['id_campo']
        tipo = request.form['tipo']
        motivo = request.form['motivo']
        observacao = request.form.get('observacao', '')

        if not all([data, setor, log, id_campo, tipo, motivo]):
            flash('Todos os campos (exceto Observação) são obrigatórios.', 'erro')
            return redirect(url_for('editar', id=id))

        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute('''
            UPDATE registros
            SET data=?, setor=?, log=?, id_campo=?, tipo=?, motivo=?, observacao=?
            WHERE id=?
        ''', (data, setor, log, id_campo, tipo, motivo, observacao, id))
        conn.commit()
        conn.close()

        flash('Registro atualizado com sucesso!', 'sucesso')
        return redirect(url_for('busca'))

    # GET: carrega dados do registro para edição
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute('SELECT * FROM registros WHERE id=?', (id,))
    registro = cur.fetchone()
    conn.close()
    if registro is None:
        flash('Registro não encontrado.', 'erro')
        return redirect(url_for('busca'))
    return render_template('cadastro.html', registro=registro)

@app.route('/excluir/<int:id>')
def excluir(id):
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute('DELETE FROM registros WHERE id=?', (id,))
    conn.commit()
    conn.close()
    flash('Registro excluído.', 'sucesso')
    return redirect(url_for('busca'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/dados_graficos')
def dados_graficos():
    conn = conectar_banco()
    cur = conn.cursor()
    # Dados por setor
    cur.execute('SELECT setor, COUNT(*) as total FROM registros GROUP BY setor')
    setor = cur.fetchall()
    # Dados por tipo
    cur.execute('SELECT tipo, COUNT(*) as total FROM registros GROUP BY tipo')
    tipo = cur.fetchall()
    # Dados por motivo
    cur.execute('SELECT motivo, COUNT(*) as total FROM registros GROUP BY motivo')
    motivo = cur.fetchall()
    conn.close()

    return jsonify({
        'setor': [{'label': r['setor'], 'total': r['total']} for r in setor],
        'tipo': [{'label': r['tipo'], 'total': r['total']} for r in tipo],
        'motivo': [{'label': r['motivo'], 'total': r['total']} for r in motivo]
    })

@app.route('/upload_logo', methods=['POST'])
def upload_logo():
    if 'logo' not in request.files:
        flash('Nenhum arquivo enviado.', 'erro')
        return redirect(url_for('cadastro'))
    file = request.files['logo']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'erro')
        return redirect(url_for('cadastro'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Salva sempre como logo.png (ou pode manter extensão original)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'logo.png'))
        flash('Logo atualizada com sucesso!', 'sucesso')
        return redirect(url_for('cadastro'))
    else:
        flash('Formato de arquivo não permitido. Use PNG, JPG, JPEG ou GIF.', 'erro')
        return redirect(url_for('cadastro'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')