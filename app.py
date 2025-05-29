import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import math
import json
import os

# Configurazione pagina
st.set_page_config(
    page_title="Loan Pricing Calculator",
    page_icon="💰",
    layout="wide"
)

# Directory per salvare i progetti
PROJECTS_DIR = "saved_projects"
if not os.path.exists(PROJECTS_DIR):
    os.makedirs(PROJECTS_DIR)

# Classe principale per i calcoli
class LoanPricingCalculator:
    def __init__(self):
        self.risk_free_rate = 0.03  # Tasso risk-free base
        
    def get_rating_from_pd(self, pd_value):
        """Converte PD in rating approssimativo"""
        rating_ranges = [
            ("AAA", 0.0000, 0.0015),
            ("AA", 0.0015, 0.0035),
            ("A", 0.0035, 0.0075),
            ("BBB", 0.0075, 0.0175),
            ("BB", 0.0175, 0.0375),
            ("B", 0.0375, 0.0750),
            ("CCC", 0.0750, 1.0000)
        ]
        
        for rating, min_pd, max_pd in rating_ranges:
            if min_pd <= pd_value < max_pd:
                return rating
        return "CCC"  # Default per PD molto alta
        
    def calculate_break_even_rate(self, loan_amount, duration_years, pd_1year, 
                                 operational_costs_pct, funding_spread, equity_cost, 
                                 capital_ratio, lgd_rate):
        """
        Calcola il tasso di pareggio secondo la metodologia MetricsLab
        """
        # Calcolo perdita attesa
        cumulative_pd = 1 - (1 - pd_1year) ** duration_years
        expected_loss = loan_amount * cumulative_pd * lgd_rate
        expected_loss_rate = expected_loss / loan_amount
        
        # Spread finanziario (copertura costo fondi)
        financial_spread = (capital_ratio * equity_cost) + ((1 - capital_ratio) * funding_spread)
        
        # Spread operativo (copertura costi operativi come % del capitale)
        operational_spread = operational_costs_pct
        
        # Spread di credito (copertura perdite attese)
        credit_spread = expected_loss_rate
        
        # Tasso di mercato base
        market_rate = self.risk_free_rate + (duration_years * 0.001)  # Curva semplificata
        
        # Tasso di pareggio
        break_even_rate = market_rate + financial_spread + operational_spread + credit_spread
        
        return {
            'market_rate': market_rate,
            'financial_spread': financial_spread,
            'operational_spread': operational_spread,
            'credit_spread': credit_spread,
            'break_even_rate': break_even_rate,
            'expected_loss': expected_loss,
            'cumulative_pd': cumulative_pd
        }
    
    def generate_amortization_schedule(self, loan_amount, annual_rate, duration_years, 
                                     payment_frequency, loan_type="fixed_amortizing", 
                                     variable_spread=0, custom_schedule=None):
        """
        Genera piano di ammortamento con più opzioni incluso custom
        """
        if loan_type == "custom" and custom_schedule is not None:
            return self.generate_custom_schedule(custom_schedule, annual_rate)
        
        # Calcolo numero rate e frequenza
        if payment_frequency == "Mensile":
            freq_per_year = 12
            days_between = 30
        elif payment_frequency == "Trimestrale":
            freq_per_year = 4
            days_between = 90
        elif payment_frequency == "Semestrale":
            freq_per_year = 2
            days_between = 180
        elif payment_frequency == "Annuale":
            freq_per_year = 1
            days_between = 365
        else:
            freq_per_year = 12  # Default mensile
            days_between = 30
        
        total_payments = int(duration_years * freq_per_year)
        periodic_rate = annual_rate / freq_per_year
        
        schedule = []
        remaining_balance = loan_amount
        
        for payment_num in range(1, total_payments + 1):
            payment_date = datetime.now() + timedelta(days=payment_num * days_between)
            
            if loan_type == "fixed_amortizing":
                # Rate costanti (capitale + interessi)
                if periodic_rate > 0:
                    monthly_payment = loan_amount * (periodic_rate * (1 + periodic_rate)**total_payments) / \
                                     ((1 + periodic_rate)**total_payments - 1)
                else:
                    monthly_payment = loan_amount / total_payments
                    
                interest_payment = remaining_balance * periodic_rate
                principal_payment = monthly_payment - interest_payment
                remaining_balance -= principal_payment
                
                schedule.append({
                    'Payment_Number': payment_num,
                    'Date': payment_date,
                    'Payment': monthly_payment,
                    'Principal': principal_payment,
                    'Interest': interest_payment,
                    'Remaining_Balance': max(0, remaining_balance)
                })
                
            elif loan_type == "variable_amortizing":
                # Tasso variabile - per semplicità assumiamo spread costante
                current_rate = self.risk_free_rate + variable_spread
                periodic_variable_rate = current_rate / freq_per_year
                
                if periodic_variable_rate > 0:
                    monthly_payment = remaining_balance * (periodic_variable_rate * (1 + periodic_variable_rate)**(total_payments - payment_num + 1)) / \
                                     ((1 + periodic_variable_rate)**(total_payments - payment_num + 1) - 1)
                else:
                    monthly_payment = remaining_balance / (total_payments - payment_num + 1)
                
                interest_payment = remaining_balance * periodic_variable_rate
                principal_payment = monthly_payment - interest_payment
                remaining_balance -= principal_payment
                
                schedule.append({
                    'Payment_Number': payment_num,
                    'Date': payment_date,
                    'Payment': monthly_payment,
                    'Principal': principal_payment,
                    'Interest': interest_payment,
                    'Remaining_Balance': max(0, remaining_balance)
                })
                
            elif loan_type in ["fixed_bullet", "variable_bullet"]:
                # Solo interessi, capitale alla fine
                if loan_type == "fixed_bullet":
                    rate_to_use = periodic_rate
                else:  # variable_bullet
                    current_rate = self.risk_free_rate + variable_spread
                    rate_to_use = current_rate / freq_per_year
                
                interest_payment = loan_amount * rate_to_use
                
                if payment_num < total_payments:
                    # Solo interessi
                    schedule.append({
                        'Payment_Number': payment_num,
                        'Date': payment_date,
                        'Payment': interest_payment,
                        'Principal': 0,
                        'Interest': interest_payment,
                        'Remaining_Balance': loan_amount
                    })
                else:
                    # Ultimo pagamento: interessi + capitale
                    schedule.append({
                        'Payment_Number': payment_num,
                        'Date': payment_date,
                        'Payment': interest_payment + loan_amount,
                        'Principal': loan_amount,
                        'Interest': interest_payment,
                        'Remaining_Balance': 0
                    })
        
        return pd.DataFrame(schedule)
    
    def generate_custom_schedule(self, custom_schedule, annual_rate):
        """
        Genera piano custom basato su date e importi definiti dall'utente
        """
        schedule = []
        
        for i, row in custom_schedule.iterrows():
            # Calcolo interessi sul saldo residuo dalla data precedente
            if i == 0:
                # Prima rata: interessi dall'inizio
                days_from_start = (row['Date'] - datetime.now()).days
                outstanding_amount = row['Saldo_Iniziale'] if 'Saldo_Iniziale' in row else sum(custom_schedule['Capitale'])
            else:
                prev_date = custom_schedule.iloc[i-1]['Date']
                days_from_start = (row['Date'] - prev_date).days
                outstanding_amount = schedule[i-1]['Remaining_Balance']
            
            # Calcolo interessi (pro-rata temporis)
            interest_payment = outstanding_amount * annual_rate * (days_from_start / 365)
            principal_payment = row['Capitale']
            remaining_balance = outstanding_amount - principal_payment
            
            schedule.append({
                'Payment_Number': i + 1,
                'Date': row['Date'],
                'Payment': principal_payment + interest_payment,
                'Principal': principal_payment,
                'Interest': interest_payment,
                'Remaining_Balance': max(0, remaining_balance)
            })
        
        return pd.DataFrame(schedule)

# Funzioni per gestione progetti
def save_project(project_data, project_name):
    """Salva un progetto in file JSON"""
    filename = f"{PROJECTS_DIR}/{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(project_data, f, indent=2, default=str)
    return filename

def load_projects():
    """Carica tutti i progetti salvati"""
    projects = []
    if os.path.exists(PROJECTS_DIR):
        for filename in os.listdir(PROJECTS_DIR):
            if filename.endswith('.json'):
                try:
                    with open(f"{PROJECTS_DIR}/{filename}", 'r') as f:
                        project = json.load(f)
                        project['filename'] = filename
                        projects.append(project)
                except Exception as e:
                    st.error(f"Errore caricamento {filename}: {e}")
    return sorted(projects, key=lambda x: x.get('created_at', ''), reverse=True)

def create_custom_schedule_template(loan_amount):
    """Crea template per piano personalizzato"""
    template_data = {
        'Data': ['2025-12-31', '2026-12-31', '2034-12-31'],
        'Capitale': [3000000, 4000000, 3000000],
        'Note': ['Primo rimborso', 'Secondo rimborso', 'Rimborso finale']
    }
    return pd.DataFrame(template_data)

# Inizializzazione calculator
calculator = LoanPricingCalculator()

# INTERFACCIA STREAMLIT
st.title("🏦 Loan Pricing Calculator - MVP")
st.markdown("### Sistema di pricing prestiti bancari basato su metodologia MetricsLab")

# Tab principale
tab1, tab2 = st.tabs(["💼 Nuovo Progetto", "📂 Progetti Salvati"])

with tab2:
    st.header("📂 Progetti Salvati")
    
    projects = load_projects()
    
    if projects:
        for i, project in enumerate(projects):
            with st.expander(f"🗂️ {project.get('project_name', 'Progetto senza nome')} - {project.get('created_at', 'Data sconosciuta')[:19]}"):
                col_info, col_actions = st.columns([3, 1])
                
                with col_info:
                    st.write(f"**Cliente/Operazione:** {project.get('project_name', 'N/A')}")
                    st.write(f"**Capitale:** €{project.get('loan_amount', 0):,}")
                    st.write(f"**Durata:** {project.get('duration_years', 0)} anni")
                    st.write(f"**PD:** {project.get('pd_1year', 0):.2%}")
                    st.write(f"**Tasso Pareggio:** {project.get('break_even_rate', 0):.2%}")
                    st.write(f"**Tasso Contrattuale:** {project.get('contractual_rate', 0):.2%}")
                
                with col_actions:
                    if st.button(f"🔄 Carica", key=f"load_{i}"):
                        # Carica i dati nel session state
                        for key, value in project.items():
                            if key not in ['filename', 'created_at']:
                                st.session_state[f"loaded_{key}"] = value
                        st.success("Progetto caricato! Vai al tab 'Nuovo Progetto'")
                        st.rerun()
    else:
        st.info("Nessun progetto salvato. Crea il tuo primo progetto nel tab 'Nuovo Progetto'!")

with tab1:
    # Sidebar per parametri di sistema
    st.sidebar.header("⚙️ Parametri di Sistema")
    
    equity_cost = st.sidebar.number_input(
        "Cost of Equity (%)", 
        min_value=0.0, max_value=100.0, 
        value=12.0, step=0.1,
        help="Rendimento richiesto sul capitale proprio"
    ) / 100
    
    capital_ratio = st.sidebar.number_input(
        "Coefficiente Patrimoniale (%)", 
        min_value=0.0, max_value=100.0, 
        value=12.0, step=0.1,
        help="Percentuale di capitale allocato sull'operazione"
    ) / 100
    
    funding_spread = st.sidebar.number_input(
        "Funding Spread (bp)", 
        min_value=0, max_value=500, 
        value=150, step=5,
        help="Spread di funding della banca in basis points"
    ) / 10000

    # Layout principale a colonne
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("📊 Input Operazione")
        
        # Nome progetto
        project_name = st.text_input(
            "Nome Progetto/Cliente", 
            value=st.session_state.get('loaded_project_name', ''),
            placeholder="es: Mutuo Casa Rossi - Milano"
        )
        
        # Struttura dell'operazione
        st.subheader("Struttura dell'Operazione")
        
        loan_amount = st.number_input(
            "Capitale (€)", 
            min_value=1000, max_value=100000000, 
            value=st.session_state.get('loaded_loan_amount', 10000000), 
            step=1000
        )
        
        # Scelta tipo di piano
        plan_type_choice = st.radio(
            "Tipo di Piano", 
            ["Piano Standard", "Piano Personalizzato"],
            help="Piano standard usa formule predefinite, Piano personalizzato permette di definire date e importi custom"
        )
        
        custom_schedule_df = None
        
        if plan_type_choice == "Piano Personalizzato":
            st.subheader("📅 Piano di Ammortamento Personalizzato")
            
            # Carica template o usa dati esistenti
            if 'custom_schedule' not in st.session_state:
                st.session_state.custom_schedule = create_custom_schedule_template(loan_amount)
            
            st.write("**Template di esempio (modificabile):**")
            st.write("Puoi modificare le date (YYYY-MM-DD) e gli importi direttamente nella tabella:")
            
            # Metodo alternativo più semplice per evitare errori
            st.write("**Inserisci i dati del piano personalizzato:**")
            
            # Numero di righe
            num_rows = st.number_input("Numero di rate/rimborsi", min_value=1, max_value=20, value=3)
            
            # Inizializza se non esiste
            if 'custom_rows' not in st.session_state:
                st.session_state.custom_rows = []
                for i in range(3):
                    default_dates = ['2025-12-31', '2026-12-31', '2034-12-31']
                    default_amounts = [3000000, 4000000, 3000000]
                    st.session_state.custom_rows.append({
                        'date': default_dates[i] if i < len(default_dates) else '2025-12-31',
                        'amount': default_amounts[i] if i < len(default_amounts) else 1000000,
                        'note': f'Rimborso {i+1}'
                    })
            
            # Aggiusta il numero di righe
            while len(st.session_state.custom_rows) < num_rows:
                st.session_state.custom_rows.append({
                    'date': '2025-12-31',
                    'amount': 1000000,
                    'note': f'Rimborso {len(st.session_state.custom_rows)+1}'
                })
            while len(st.session_state.custom_rows) > num_rows:
                st.session_state.custom_rows.pop()
            
            # Input per ogni riga
            for i in range(num_rows):
                st.write(f"**Rimborso {i+1}:**")
                col1, col2, col3 = st.columns([2, 2, 3])
                
                with col1:
                    st.session_state.custom_rows[i]['date'] = st.text_input(
                        f"Data {i+1}", 
                        value=st.session_state.custom_rows[i]['date'],
                        placeholder="YYYY-MM-DD",
                        key=f"date_{i}"
                    )
                
                with col2:
                    st.session_state.custom_rows[i]['amount'] = st.number_input(
                        f"Importo €", 
                        value=st.session_state.custom_rows[i]['amount'],
                        min_value=0,
                        step=1000,
                        key=f"amount_{i}"
                    )
                
                with col3:
                    st.session_state.custom_rows[i]['note'] = st.text_input(
                        f"Note", 
                        value=st.session_state.custom_rows[i]['note'],
                        key=f"note_{i}"
                    )
            
            # Crea il DataFrame
            try:
                edited_schedule = pd.DataFrame({
                    'Data': [row['date'] for row in st.session_state.custom_rows],
                    'Capitale': [row['amount'] for row in st.session_state.custom_rows],
                    'Note': [row['note'] for row in st.session_state.custom_rows]
                })
            except Exception as e:
                st.error(f"Errore nella creazione del piano: {e}")
                edited_schedule = create_custom_schedule_template(loan_amount)
            
            # Validazione
            total_custom_capital = edited_schedule['Capitale'].sum()
            if abs(total_custom_capital - loan_amount) > 1:
                st.warning(f"⚠️ Attenzione: Totale capitale nel piano (€{total_custom_capital:,}) diverso dal capitale totale (€{loan_amount:,})")
            else:
                st.success(f"✅ Piano bilanciato: €{total_custom_capital:,}")
            
            # Converti date da string a datetime
            try:
                edited_schedule['Date'] = pd.to_datetime(edited_schedule['Data'])
                custom_schedule_df = edited_schedule.sort_values('Date')
                st.session_state.custom_schedule = edited_schedule
                loan_type = "custom"
                
                # Calcola durata approssimativa per altri calcoli
                duration_years = (custom_schedule_df['Date'].max() - datetime.now()).days / 365.25
                payment_frequency = "Custom"
                
            except Exception as e:
                st.error(f"Errore nel formato delle date: {e}")
                custom_schedule_df = None
                loan_type = "fixed_amortizing"
                duration_years = 5
                payment_frequency = "Mensile"
                
        else:
            # Piano standard
            # Durata in anni come numero
            duration_years = st.number_input(
                "Durata (anni)", 
                min_value=0.25, max_value=50.0, 
                value=float(st.session_state.get('loaded_duration_years', 10)), 
                step=0.25,
                help="Durata del prestito in anni (es: 2.5 per 2 anni e 6 mesi)"
            )
            
            # Tipo di piano con variable bullet
            loan_type = st.selectbox("Tipo di Piano", [
                "fixed_amortizing", 
                "variable_amortizing",
                "fixed_bullet",
                "variable_bullet"
            ], index=0, help="Tipo di piano di rimborso")
            
            # Frequenza pagamenti
            payment_frequency = st.selectbox(
                "Frequenza Rate", 
                ["Mensile", "Trimestrale", "Semestrale", "Annuale"],
                index=0,
                help="Frequenza di pagamento delle rate"
            )
        
        # Spread variabile (solo se tasso variabile)
        variable_spread = 0
        if loan_type in ["variable_amortizing", "variable_bullet"]:
            variable_spread = st.number_input(
                "Spread Tasso Variabile (bp)", 
                min_value=0, max_value=1000, 
                value=200, step=5,
                help="Spread applicato al tasso base per il variabile"
            ) / 10000
        
        # Rating e rischio
        st.subheader("Rating e Rischio")
        
        # Opzione per inserire PD direttamente
        use_rating = st.radio("Inserimento Rischio", ["Usa Rating Standard", "Inserisci PD"])
        
        if use_rating == "Usa Rating Standard":
            rating_options = {
                "AAA": 0.0010,
                "AA": 0.0025, 
                "A": 0.0050,
                "BBB": 0.0100,
                "BB": 0.0250,
                "B": 0.0500,
                "CCC": 0.1000
            }
            
            loaded_rating = st.session_state.get('loaded_rating_class', 'BBB')
            rating_index = list(rating_options.keys()).index(loaded_rating) if loaded_rating in rating_options else 3
            rating_class = st.selectbox("Rating Class", list(rating_options.keys()), index=rating_index)
            pd_1year = rating_options[rating_class]
            st.info(f"PD a 1 anno: {pd_1year:.2%}")
        else:
            pd_1year = st.number_input(
                "Probabilità di Default a 1 anno (%)",
                min_value=0.01, max_value=50.0,
                value=st.session_state.get('loaded_pd_1year', 1.0),
                step=0.01,
                help="Probabilità di default a 12 mesi in percentuale"
            ) / 100
            
            # Mostra rating equivalente
            equivalent_rating = calculator.get_rating_from_pd(pd_1year)
            st.info(f"Rating equivalente: {equivalent_rating}")
            rating_class = equivalent_rating
        
        # LGD come numero 0-100
        lgd_rate = st.number_input(
            "Loss Given Default (%)", 
            min_value=0.0, max_value=100.0,
            value=st.session_state.get('loaded_lgd_rate', 45.0),
            step=1.0,
            help="Perdita in caso di default in percentuale"
        ) / 100
        
        # Costi operativi come percentuale
        st.subheader("Costi Operativi")
        operational_costs_pct = st.number_input(
            "Costi Operativi (% del capitale)", 
            min_value=0.0, max_value=10.0,
            value=st.session_state.get('loaded_operational_costs_pct', 0.5),
            step=0.01,
            help="Costi operativi totali come percentuale del capitale"
        ) / 100
        
        # Commissioni
        st.subheader("Commissioni Attive")
        
        # Commissioni iniziali
        initial_commission_type = st.radio("Commissioni Iniziali", ["Valore Assoluto (€)", "Percentuale del Capitale (%)"])
        
        if initial_commission_type == "Valore Assoluto (€)":
            initial_commission = st.number_input(
                "Commissioni Iniziali (€)", 
                min_value=0.0, max_value=1000000.0,
                value=st.session_state.get('loaded_initial_commission', 0.0),
                step=100.0
            )
            initial_commission_pct = initial_commission / loan_amount
        else:
            initial_commission_pct = st.number_input(
                "Commissioni Iniziali (% del capitale)", 
                min_value=0.0, max_value=5.0,
                value=st.session_state.get('loaded_initial_commission_pct', 0.0),
                step=0.01
            ) / 100
            initial_commission = initial_commission_pct * loan_amount
        
        # Commissioni annue
        annual_commission_type = st.radio("Commissioni Annue", ["Valore Assoluto (€)", "Percentuale del Capitale (%)"])
        
        if annual_commission_type == "Valore Assoluto (€)":
            annual_commission = st.number_input(
                "Commissioni Annue (€)", 
                min_value=0.0, max_value=500000.0,
                value=st.session_state.get('loaded_annual_commission', 0.0),
                step=50.0
            )
            annual_commission_pct = annual_commission / loan_amount
        else:
            annual_commission_pct = st.number_input(
                "Commissioni Annue (% del capitale)", 
                min_value=0.0, max_value=2.0,
                value=st.session_state.get('loaded_annual_commission_pct', 0.0),
                step=0.01
            ) / 100
            annual_commission = annual_commission_pct * loan_amount
        
        total_commissions = initial_commission + (annual_commission * duration_years)

    with col2:
        st.header("📈 Risultati Calcolo")
        
        # Calcolo tasso di pareggio
        pricing_results = calculator.calculate_break_even_rate(
            loan_amount, duration_years, pd_1year, 
            operational_costs_pct, funding_spread, equity_cost,
            capital_ratio, lgd_rate
        )
        
        # Visualizzazione risultati
        st.subheader("Breakdown del Tasso di Pareggio")
        
        # Metriche principali
        st.metric("Tasso di Pareggio", f"{pricing_results['break_even_rate']:.2%}")
        st.metric("Tasso di Mercato", f"{pricing_results['market_rate']:.2%}")
        st.metric("Perdita Attesa", f"€{pricing_results['expected_loss']:,.0f}")
        st.metric("PD Cumulata", f"{pricing_results['cumulative_pd']:.2%}")
        
        # Commissioni info
        if total_commissions > 0:
            st.info(f"💰 Commissioni Totali: €{total_commissions:,.0f}")
        
        # Breakdown spreads
        spreads_data = {
            'Componente': ['Tasso Mercato', 'Spread Finanziario', 'Spread Operativo', 'Spread Credito'],
            'Valore (%)': [
                pricing_results['market_rate'] * 100,
                pricing_results['financial_spread'] * 100,
                pricing_results['operational_spread'] * 100,
                pricing_results['credit_spread'] * 100
            ]
        }
        
        fig_breakdown = px.bar(
            spreads_data, 
            x='Componente', 
            y='Valore (%)',
            title="Breakdown del Tasso di Pareggio",
            color='Componente'
        )
        st.plotly_chart(fig_breakdown, use_container_width=True)

    # Sezione Piano di Ammortamento
    st.header("📋 Piano di Ammortamento")

    # Input per tasso contrattuale
    st.subheader("Tasso Contrattuale")
    
    default_contractual = st.session_state.get('loaded_contractual_rate', pricing_results['break_even_rate'] * 100)
    contractual_rate_input = st.number_input(
        "Tasso Contrattuale (%)", 
        min_value=0.0, max_value=30.0, 
        value=default_contractual,
        step=0.01
    ) / 100

    commercial_spread = contractual_rate_input - pricing_results['break_even_rate']
    st.metric("Spread Commerciale", f"{commercial_spread:.2%}")

    # Genera piano di ammortamento
    try:
        schedule_df = calculator.generate_amortization_schedule(
            loan_amount, contractual_rate_input, duration_years, 
            payment_frequency, loan_type, variable_spread, custom_schedule_df
        )
        
        # Calcolo margine commerciale
        total_interest = schedule_df['Interest'].sum()
        break_even_schedule = calculator.generate_amortization_schedule(
            loan_amount, pricing_results['break_even_rate'], duration_years, 
            payment_frequency, loan_type, variable_spread, custom_schedule_df
        )
        break_even_interest = break_even_schedule['Interest'].sum()
        commercial_margin = total_interest - break_even_interest + total_commissions

        # Visualizzazione margine
        st.subheader("Analisi Economica")
        
        st.metric("Interessi Totali", f"€{total_interest:,.0f}")
        st.metric("Commissioni", f"€{total_commissions:,.0f}")
        st.metric("Ricavi Totali", f"€{total_interest + total_commissions:,.0f}")
        st.metric("Margine Commerciale", f"€{commercial_margin:,.0f}")

        # Piano di ammortamento completo con scroll
        st.subheader("Piano di Ammortamento Completo")
        
        # Prepara dataframe per visualizzazione
        display_schedule = schedule_df.copy()
        display_schedule['Date'] = display_schedule['Date'].dt.strftime('%Y-%m-%d')
        display_schedule['Payment'] = display_schedule['Payment'].round(2)
        display_schedule['Principal'] = display_schedule['Principal'].round(2)
        display_schedule['Interest'] = display_schedule['Interest'].round(2)
        display_schedule['Remaining_Balance'] = display_schedule['Remaining_Balance'].round(2)
        
        # Container con altezza fissa e scroll
        st.dataframe(
            display_schedule, 
            use_container_width=True,
            height=300  # Altezza fissa con scroll automatico
        )

        # Grafico evoluzione saldo
        fig_balance = go.Figure()
        fig_balance.add_trace(go.Scatter(
            x=schedule_df['Payment_Number'],
            y=schedule_df['Remaining_Balance'],
            mode='lines',
            name='Saldo Residuo',
            line=dict(color='blue', width=2)
        ))

        fig_balance.update_layout(
            title="Evoluzione Saldo Residuo",
            xaxis_title="Numero Rata",
            yaxis_title="Saldo Residuo (€)",
            hovermode='x'
        )

        st.plotly_chart(fig_balance, use_container_width=True)

    except Exception as e:
        st.error(f"Errore nella generazione del piano di ammortamento: {e}")
        st.write("Verifica i dati inseriti, in particolare le date nel piano personalizzato.")

    # Salvataggio progetto
    st.subheader("💾 Salva Progetto")
    
    if st.button("💾 Salva Progetto", type="primary"):
        if project_name:
            try:
                project_data = {
                    'project_name': project_name,
                    'created_at': datetime.now().isoformat(),
                    'loan_amount': loan_amount,
                    'duration_years': duration_years,
                    'loan_type': loan_type,
                    'payment_frequency': payment_frequency,
                    'rating_class': rating_class,
                    'pd_1year': pd_1year,
                    'lgd_rate': lgd_rate,
                    'operational_costs_pct': operational_costs_pct,
                    'initial_commission': initial_commission,
                    'annual_commission': annual_commission,
                    'contractual_rate': contractual_rate_input * 100,
                    'break_even_rate': pricing_results['break_even_rate'],
                    'commercial_margin': commercial_margin if 'commercial_margin' in locals() else 0,
                    'total_interest': total_interest if 'total_interest' in locals() else 0,
                    'total_commissions': total_commissions,
                    'expected_loss': pricing_results['expected_loss'],
                    'equity_cost': equity_cost,
                    'capital_ratio': capital_ratio,
                    'funding_spread': funding_spread,
                    'plan_type': plan_type_choice,
                    'custom_schedule': custom_schedule_df.to_dict('records') if custom_schedule_df is not None else None
                }
                
                filename = save_project(project_data, project_name)
                st.success(f"✅ Progetto salvato come: {filename}")
                
                # Pulisci session state per loaded values
                keys_to_clear = [key for key in st.session_state.keys() if key.startswith('loaded_')]
                for key in keys_to_clear:
                    del st.session_state[key]
                    
            except Exception as e:
                st.error(f"Errore nel salvataggio: {e}")
        else:
            st.error("⚠️ Inserisci un nome per il progetto!")

# Footer
st.markdown("---")
st.markdown("💡 **Loan Pricing Calculator** - Sistema per analisi e pricing prestiti bancari")
st.markdown(f"🔧 Progetti salvati: {len(load_projects())}")
