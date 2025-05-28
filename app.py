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
        
    def calculate_break_even_rate(self, loan_amount, duration_years, rating_class, 
                                 operational_costs, funding_spread, equity_cost, 
                                 capital_ratio, expected_loss_rate):
        """
        Calcola il tasso di pareggio secondo la metodologia MetricsLab
        """
        # Spread finanziario (copertura costo fondi)
        financial_spread = (capital_ratio * equity_cost) + ((1 - capital_ratio) * funding_spread)
        
        # Spread operativo (copertura costi operativi)
        operational_spread = operational_costs / loan_amount
        
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
            'break_even_rate': break_even_rate
        }
    
    def generate_amortization_schedule(self, loan_amount, annual_rate, duration_years, 
                                     payment_frequency=12, loan_type="fixed_amortizing"):
        """
        Genera piano di ammortamento
        """
        total_payments = duration_years * payment_frequency
        monthly_rate = annual_rate / payment_frequency
        
        if loan_type == "fixed_amortizing":
            # Rate costanti (capitale + interessi)
            if monthly_rate > 0:
                monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate)**total_payments) / \
                                 ((1 + monthly_rate)**total_payments - 1)
            else:
                monthly_payment = loan_amount / total_payments
                
            schedule = []
            remaining_balance = loan_amount
            
            for payment_num in range(1, total_payments + 1):
                interest_payment = remaining_balance * monthly_rate
                principal_payment = monthly_payment - interest_payment
                remaining_balance -= principal_payment
                
                # Data di pagamento
                payment_date = datetime.now() + timedelta(days=payment_num * 30)
                
                schedule.append({
                    'Payment_Number': payment_num,
                    'Date': payment_date,
                    'Payment': monthly_payment,
                    'Principal': principal_payment,
                    'Interest': interest_payment,
                    'Remaining_Balance': max(0, remaining_balance)
                })
                
        elif loan_type == "fixed_bullet":
            # Solo interessi, capitale alla fine
            monthly_interest = loan_amount * monthly_rate
            schedule = []
            
            for payment_num in range(1, total_payments + 1):
                payment_date = datetime.now() + timedelta(days=payment_num * 30)
                
                if payment_num < total_payments:
                    # Solo interessi
                    schedule.append({
                        'Payment_Number': payment_num,
                        'Date': payment_date,
                        'Payment': monthly_interest,
                        'Principal': 0,
                        'Interest': monthly_interest,
                        'Remaining_Balance': loan_amount
                    })
                else:
                    # Ultimo pagamento: interessi + capitale
                    schedule.append({
                        'Payment_Number': payment_num,
                        'Date': payment_date,
                        'Payment': monthly_interest + loan_amount,
                        'Principal': loan_amount,
                        'Interest': monthly_interest,
                        'Remaining_Balance': 0
                    })
        
        return pd.DataFrame(schedule)
    
    def calculate_expected_loss(self, loan_amount, pd_1year, lgd_rate, duration_years):
        """
        Calcola perdita attesa semplificata
        """
        # Modello semplificato: PD cresce nel tempo
        cumulative_pd = 1 - (1 - pd_1year) ** duration_years
        expected_loss = loan_amount * cumulative_pd * lgd_rate
        return expected_loss, cumulative_pd

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

def load_project(filename):
    """Carica un progetto specifico"""
    try:
        with open(f"{PROJECTS_DIR}/{filename}", 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Errore nel caricamento del progetto: {e}")
        return None

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
                    st.write(f"**Rating:** {project.get('rating_class', 'N/A')}")
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
    equity_cost = st.sidebar.slider("Cost of Equity (%)", 8.0, 15.0, 12.0, 0.1) / 100
    capital_ratio = st.sidebar.slider("Coefficiente Patrimoniale (%)", 8.0, 20.0, 12.0, 0.1) / 100
    funding_spread_bp = st.sidebar.slider("Funding Spread (bp)", 50, 300, 150, 10)
    funding_spread = funding_spread_bp / 10000

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
            10000, 10000000, 
            st.session_state.get('loaded_loan_amount', 500000), 
            10000
        )
        duration_years = st.slider(
            "Durata (anni)", 
            1, 30, 
            st.session_state.get('loaded_duration_years', 10)
        )
        
        loan_type = st.selectbox("Tipo di Piano", [
            "fixed_amortizing", 
            "fixed_bullet"
        ], index=0 if st.session_state.get('loaded_loan_type', 'fixed_amortizing') == 'fixed_amortizing' else 1)
        
        # Rating e rischio
        st.subheader("Rating e Rischio")
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
        
        lgd_rate = st.slider(
            "Loss Given Default (%)", 
            20, 80, 
            int(st.session_state.get('loaded_lgd_rate', 0.45) * 100)
        ) / 100
        
        # Costi operativi
        st.subheader("Costi Operativi")
        initial_costs = st.number_input(
            "Costi Iniziali (€)", 
            0, 50000, 
            st.session_state.get('loaded_initial_costs', 2000)
        )
        annual_costs = st.number_input(
            "Costi Annui (€)", 
            0, 10000, 
            st.session_state.get('loaded_annual_costs', 500)
        )
        
        total_operational_costs = initial_costs + (annual_costs * duration_years)

    with col2:
        st.header("📈 Risultati Calcolo")
        
        # Calcolo perdita attesa
        expected_loss, cumulative_pd = calculator.calculate_expected_loss(
            loan_amount, pd_1year, lgd_rate, duration_years
        )
        expected_loss_rate = expected_loss / loan_amount
        
        # Calcolo tasso di pareggio
        pricing_results = calculator.calculate_break_even_rate(
            loan_amount, duration_years, rating_class, 
            total_operational_costs, funding_spread, equity_cost,
            capital_ratio, expected_loss_rate
        )
        
        # Visualizzazione risultati
        st.subheader("Breakdown del Tasso di Pareggio")
        
        # Metriche principali
        col2a, col2b = st.columns(2)
        
        with col2a:
            st.metric("Tasso di Pareggio", f"{pricing_results['break_even_rate']:.2%}")
            st.metric("Tasso di Mercato", f"{pricing_results['market_rate']:.2%}")
            
        with col2b:
            st.metric("Perdita Attesa", f"€{expected_loss:,.0f}")
            st.metric("PD Cumulata", f"{cumulative_pd:.2%}")
        
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
    col3a, col3b = st.columns(2)

    with col3a:
        default_contractual = st.session_state.get('loaded_contractual_rate', pricing_results['break_even_rate'] * 100)
        contractual_rate_input = st.number_input(
            "Tasso Contrattuale (%)", 
            0.0, 20.0, 
            default_contractual,
            0.01
        ) / 100

    with col3b:
        commercial_spread = contractual_rate_input - pricing_results['break_even_rate']
        st.metric("Spread Commerciale", f"{commercial_spread:.2%}")

    # Genera piano di ammortamento
    schedule_df = calculator.generate_amortization_schedule(
        loan_amount, contractual_rate_input, duration_years, 12, loan_type
    )

    # Calcolo margine commerciale
    total_interest = schedule_df['Interest'].sum()
    break_even_schedule = calculator.generate_amortization_schedule(
        loan_amount, pricing_results['break_even_rate'], duration_years, 12, loan_type
    )
    break_even_interest = break_even_schedule['Interest'].sum()
    commercial_margin = total_interest - break_even_interest

    # Visualizzazione margine
    st.subheader("Analisi Economica")
    col4a, col4b, col4c = st.columns(3)

    with col4a:
        st.metric("Interessi Totali", f"€{total_interest:,.0f}")
        
    with col4b:
        st.metric("Interessi Pareggio", f"€{break_even_interest:,.0f}")
        
    with col4c:
        st.metric("Margine Commerciale", f"€{commercial_margin:,.0f}")

    # Salvataggio progetto
    st.subheader("💾 Salva Progetto")
    col_save, col_export = st.columns(2)
    
    with col_save:
        if st.button("💾 Salva Progetto", type="primary"):
            if project_name:
                project_data = {
                    'project_name': project_name,
                    'created_at': datetime.now().isoformat(),
                    'loan_amount': loan_amount,
                    'duration_years': duration_years,
                    'loan_type': loan_type,
                    'rating_class': rating_class,
                    'lgd_rate': lgd_rate,
                    'initial_costs': initial_costs,
                    'annual_costs': annual_costs,
                    'contractual_rate': contractual_rate_input * 100,  # Salva in percentuale
                    'break_even_rate': pricing_results['break_even_rate'],
                    'commercial_margin': commercial_margin,
                    'total_interest': total_interest,
                    'expected_loss': expected_loss,
                    'equity_cost': equity_cost,
                    'capital_ratio': capital_ratio,
                    'funding_spread': funding_spread
                }
                
                filename = save_project(project_data, project_name)
                st.success(f"✅ Progetto salvato come: {filename}")
                
                # Pulisci session state per loaded values
                keys_to_clear = [key for key in st.session_state.keys() if key.startswith('loaded_')]
                for key in keys_to_clear:
                    del st.session_state[key]
            else:
                st.error("⚠️ Inserisci un nome per il progetto!")

    # Visualizzazione piano ammortamento (prime 12 rate)
    st.subheader("Piano di Ammortamento (Prime 12 Rate)")
    display_schedule = schedule_df.head(12).copy()
    display_schedule['Date'] = display_schedule['Date'].dt.strftime('%Y-%m-%d')
    display_schedule['Payment'] = display_schedule['Payment'].round(2)
    display_schedule['Principal'] = display_schedule['Principal'].round(2)
    display_schedule['Interest'] = display_schedule['Interest'].round(2)
    display_schedule['Remaining_Balance'] = display_schedule['Remaining_Balance'].round(2)

    st.dataframe(display_schedule, use_container_width=True)

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

# Footer
st.markdown("---")
st.markdown("💡 **Loan Pricing Calculator** - Sistema per analisi e pricing prestiti bancari")
st.markdown(f"🔧 Progetti salvati: {len(load_projects())}")