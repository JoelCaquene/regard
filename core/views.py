from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction # IMPORTANTE: Adicionado para transações seguras
import random
from datetime import date, datetime, time, timedelta # Importação completa
from django.utils import timezone # Adicionado para garantir o uso de timezone-aware datetimes
from decimal import Decimal # <--- IMPORTANTE: Adicionado para corrigir o TypeError

from .forms import RegisterForm, DepositForm, WithdrawalForm, BankDetailsForm
from .models import PlatformSettings, CustomUser, Level, UserLevel, BankDetails, Deposit, Withdrawal, Task, PlatformBankDetails, Roulette, RouletteSettings


# --- NOVA FUNÇÃO DE LÓGICA (Ganho de 24 horas) ---
@transaction.atomic # Garante que as operações de banco de dados sejam seguras
def check_and_apply_daily_gain(user):
    """
    Verifica e aplica o ganho de 24 horas ao saldo do usuário, se devido.
    
    ESTA FUNÇÃO REQUER O CAMPO 'last_daily_gain_date' NO MODELO UserLevel.
    
    Retorna (boolean, datetime_do_proximo_ganho)
    """
    # Usamos select_for_update para bloquear a linha, garantindo que o ganho não seja duplicado
    active_user_level = UserLevel.objects.select_for_update().filter(user=user, is_active=True).first()
    
    if not active_user_level:
        return False, None

    level = active_user_level.level
    now = timezone.now()
    
    # Define o tempo de espera (24 horas)
    COOLDOWN_DURATION = timedelta(hours=24) 
    
    # Se o 'last_daily_gain_date' for None (primeiro acesso), usamos a data de compra como referência.
    last_gain_time = active_user_level.last_daily_gain_date or active_user_level.purchase_date
    next_gain_time = last_gain_time + COOLDOWN_DURATION

    # 1. Verifica se já é hora de aplicar o ganho
    if now >= next_gain_time:
        
        daily_gain_amount = level.daily_gain
        
        # 2. Aplicar o ganho ao saldo do usuário
        user.available_balance += daily_gain_amount
        user.save()
        
        # 3. Registrar o último ganho no UserLevel e criar um registro de Task (para histórico)
        active_user_level.last_daily_gain_date = now # Zera o contador para o próximo ciclo
        active_user_level.save()
        
        # Cria um registro de tarefa concluída (para fins de histórico e totalização)
        Task.objects.create(
            user=user, 
            # CORREÇÃO CRÍTICA: Agora passamos NONE, pois este ganho não é associado a uma TaskDefinition.
            # O erro estava aqui: 'task_definition=Task.objects.first()', que retornava um objeto Task.
            task_definition=None, 
            earnings=daily_gain_amount
        )
        
        # O próximo ganho será 24h a partir de agora
        next_gain_time_new = now + COOLDOWN_DURATION
        return True, next_gain_time_new
    
    # Se não for hora de gerar o ganho
    return False, next_gain_time
# --- FIM DA NOVA FUNÇÃO DE LÓGICA ---


# --- FUNÇÃO ATUALIZADA ---
def home(request):
    if request.user.is_authenticated:
        return redirect('menu')
    else:
        return redirect('cadastro')
# --- FIM DA FUNÇÃO ATUALIZADA ---

# --- NOVA FUNÇÃO ADICIONADA PARA RESOLVER O NoReverseMatch ---
@login_required
def download_app(request):
    """
    View para o link de download do aplicativo. 
    Redireciona para o link configurado ou para um placeholder.
    """
    try:
        # Tenta obter o link de download configurado nas PlatformSettings
        app_link = PlatformSettings.objects.first().app_download_link
        if app_link:
            return redirect(app_link)
    except (PlatformSettings.DoesNotExist, AttributeError):
        pass # Ignora se a configuração não existe ou não tem o campo
        
    # Se não houver link configurado ou a configuração falhar, usa um placeholder temporário
    # ATENÇÃO: Você deve configurar o 'app_download_link' no modelo PlatformSettings no Admin.
    return redirect('https://seulinkdedownload.com')
# --- FIM DA NOVA FUNÇÃO ---

def menu(request):
    user_level = None
    levels = Level.objects.all().order_by('deposit_value')

    if request.user.is_authenticated:
        user_level = UserLevel.objects.filter(user=request.user, is_active=True).first()

    try:
        platform_settings = PlatformSettings.objects.first()
        whatsapp_link = platform_settings.whatsapp_link
        # --- ADIÇÃO DO LINK DO TELEGRAM AQUI ---
        telegram_link = getattr(platform_settings, 'telegram_link', '#') 
    except (PlatformSettings.DoesNotExist, AttributeError):
        whatsapp_link = '#'
        telegram_link = '#' # Valor padrão se as configurações não existirem

    context = {
        'user_level': user_level,
        'levels': levels,
        'whatsapp_link': whatsapp_link,
        'telegram_link': telegram_link, # Passando o link do Telegram para o template
    }
    return render(request, 'menu.html', context)

def cadastro(request):
    invite_code_from_url = request.GET.get('invite', None)

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            
            # --- CORREÇÃO AQUI: O NOME DO CAMPO NO FORM É 'invited_by_code' ---
            invited_by_code = form.cleaned_data.get('invited_by_code')
            
            if invited_by_code:
                try:
                    invited_by_user = CustomUser.objects.get(invite_code=invited_by_code)
                    user.invited_by = invited_by_user
                except CustomUser.DoesNotExist:
                    messages.error(request, 'Código de convite inválido.')
                    return render(request, 'cadastro.html', {'form': form})
                
            user.save()
            login(request, user)
            return redirect('menu')
        else:
            try:
                whatsapp_link = PlatformSettings.objects.first().whatsapp_link
            except (PlatformSettings.DoesNotExist, AttributeError):
                whatsapp_link = '#'
            return render(request, 'cadastro.html', {'form': form, 'whatsapp_link': whatsapp_link})
    else:
        # --- CORREÇÃO AQUI: O NOME DO CAMPO NO FORM É 'invited_by_code' ---
        if invite_code_from_url:
            form = RegisterForm(initial={'invited_by_code': invite_code_from_url})
        else:
            form = RegisterForm()
    
    try:
        whatsapp_link = PlatformSettings.objects.first().whatsapp_link
    except (PlatformSettings.DoesNotExist, AttributeError):
        whatsapp_link = '#'

    return render(request, 'cadastro.html', {'form': form, 'whatsapp_link': whatsapp_link})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('menu')
    else:
        form = AuthenticationForm()

    try:
        whatsapp_link = PlatformSettings.objects.first().whatsapp_link
    except (PlatformSettings.DoesNotExist, AttributeError):
        whatsapp_link = '#'

    return render(request, 'login.html', {'form': form, 'whatsapp_link': whatsapp_link})

@login_required
def user_logout(request):
    logout(request)
    return redirect('menu')

# --- FUNÇÃO DE DEPÓSITO ATUALIZADA PARA O NOVO FLUXO ---
@login_required
def deposito(request):
    platform_bank_details = PlatformBankDetails.objects.all()
    deposit_instruction = PlatformSettings.objects.first().deposit_instruction if PlatformSettings.objects.first() else 'Instruções de depósito não disponíveis.'
    
    # Busca todos os valores de depósito dos Níveis para a Etapa 2
    level_deposits = Level.objects.all().values_list('deposit_value', flat=True).distinct().order_by('deposit_value')
    # Converte os Decimais para strings formatadas para JS
    level_deposits_list = [str(d) for d in level_deposits] 

    if request.method == 'POST':
        # O formulário agora é submetido na Etapa 3
        # Os campos 'amount' e 'proof_of_payment' são necessários
        form = DepositForm(request.POST, request.FILES)
        if form.is_valid():
            deposit = form.save(commit=False)
            deposit.user = request.user
            deposit.save()
            
            # Não exibe mensagem aqui, mas sim no template
            # O template irá exibir uma tela de sucesso após a submissão
            return render(request, 'deposito.html', {
                'platform_bank_details': platform_bank_details,
                'deposit_instruction': deposit_instruction,
                'level_deposits_list': level_deposits_list,
                'deposit_success': True # Variável de contexto para a tela de sucesso
            })
        else:
            messages.error(request, 'Erro ao enviar o depósito. Verifique o valor e o comprovativo.')
    
    # Se não for POST ou se for a primeira vez acessando a página
    form = DepositForm()
    
    context = {
        'platform_bank_details': platform_bank_details,
        'deposit_instruction': deposit_instruction,
        'form': form,
        'level_deposits_list': level_deposits_list,
        'deposit_success': False, # Estado inicial
    }
    return render(request, 'deposito.html', context)
# --- FIM DA FUNÇÃO DE DEPÓSITO ATUALIZADA ---

@login_required
def approve_deposit(request, deposit_id):
    if not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para realizar esta ação.')
        return redirect('menu')

    deposit = get_object_or_404(Deposit, id=deposit_id)
    if not deposit.is_approved:
        deposit.is_approved = True
        deposit.save()
        deposit.user.available_balance += deposit.amount
        deposit.user.save()
        messages.success(request, f'Depósito de {deposit.amount} KZ aprovado para {deposit.user.phone_number}. Saldo atualizado.')
    
    return redirect('renda')

# --- FUNÇÃO DE SAQUE ATUALIZADA COM NOVAS REGRAS ---
@login_required
def saque(request):
    # NOVOS PARÂMETROS DE SAQUE
    MIN_WITHDRAWAL_AMOUNT = Decimal('2000') # Usado como Decimal por ser valor monetário
    START_TIME = time(9, 0, 0) # 09:00:00
    END_TIME = time(18, 0, 0) # 18:00:00
    # FIM DOS NOVOS PARÂMETROS

    withdrawal_instruction = PlatformSettings.objects.first().withdrawal_instruction if PlatformSettings.objects.first() else 'Instruções de saque não disponíveis.'
    
    withdrawal_records = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    
    has_bank_details = BankDetails.objects.filter(user=request.user).exists()
    
    # Verifica se o saque está dentro do horário permitido
    now = datetime.now().time()
    is_time_allowed = START_TIME <= now <= END_TIME

    # Verifica se já houve saque hoje
    today = date.today()
    already_withdrawn_today = Withdrawal.objects.filter(
        user=request.user, 
        created_at__date=today
    ).exists()
    
    if request.method == 'POST':
        form = WithdrawalForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            
            if not has_bank_details:
                messages.error(request, 'Por favor, adicione suas coordenadas bancárias no seu perfil antes de solicitar um saque.')
                return redirect('perfil')
            
            if not is_time_allowed:
                messages.error(request, f'O saque só é permitido entre as {START_TIME.strftime("%H:%M")}h e as {END_TIME.strftime("%H:%M")}h.')
            elif already_withdrawn_today:
                messages.error(request, 'Você só pode realizar um saque por dia.')
            elif amount < MIN_WITHDRAWAL_AMOUNT: # Mínimo atualizado
                messages.error(request, f'O valor mínimo para saque é {MIN_WITHDRAWAL_AMOUNT} KZ.')
            elif request.user.available_balance < amount:
                messages.error(request, 'Saldo insuficiente.')
            else:
                # Todas as regras de negócio foram atendidas
                withdrawal = Withdrawal.objects.create(user=request.user, amount=amount)
                request.user.available_balance -= amount
                request.user.save()
                messages.success(request, 'Saque solicitado com sucesso. Aguarde a aprovação.')
                return redirect('saque')
        # Se o formulário não for válido, as mensagens de erro do formulário (se houver) serão tratadas implicitamente.
    else:
        form = WithdrawalForm()

    context = {
        'withdrawal_instruction': withdrawal_instruction,
        'withdrawal_records': withdrawal_records,
        'form': form,
        'has_bank_details': has_bank_details,
        'min_withdrawal_amount': MIN_WITHDRAWAL_AMOUNT, # Passa o novo mínimo para o template
        'is_time_allowed': is_time_allowed, # Passa se está no horário
        'already_withdrawn_today': already_withdrawn_today # Passa se já sacou hoje
    }
    return render(request, 'saque.html', context)
# --- FIM DA FUNÇÃO DE SAQUE ATUALIZADA ---


# --- FUNÇÃO TAREFA COMPLETAMENTE SUBSTITUÍDA PELA LÓGICA DE 24H ---
@login_required
def tarefa(request):
    user = request.user
    
    # 1. Tenta aplicar o ganho se 24h se passaram
    gain_applied, next_gain_time = check_and_apply_daily_gain(user)
    
    # 2. Encontra o nível ativo (novamente, se necessário para o template)
    active_user_level = UserLevel.objects.filter(user=user, is_active=True).first()
    
    cooldown_seconds_remaining = 0 # Inicializa
    
    if active_user_level and next_gain_time:
        now = timezone.now()
        
        if next_gain_time > now:
            # Calcula o tempo restante real até o próximo ganho
            time_remaining = next_gain_time - now
            cooldown_seconds_remaining = int(time_remaining.total_seconds())
        else:
            # Se o ganho deveria ter sido aplicado mas por algum motivo falhou (ou não tem nível)
            cooldown_seconds_remaining = 0

    context = {
        'has_active_level': active_user_level is not None,
        'active_level': active_user_level,
        'level': active_user_level.level if active_user_level else None, # Passamos o objeto Level
        'cooldown_seconds_remaining': cooldown_seconds_remaining, # Tempo real restante
        'gain_applied': gain_applied, # Indica se um ganho acabou de ser aplicado
    }
    return render(request, 'tarefa.html', context)
# --- FIM DA FUNÇÃO TAREFA SUBSTITUÍDA ---


# ATENÇÃO: AS FUNÇÕES process_task E check_and_generate_gain FORAM REMOVIDAS
# PORQUE A NOVA LÓGICA DE 24H AS TORNA DESNECESSÁRIAS.


# --- FUNÇÃO NIVEL ATUALIZADA COM CORREÇÃO DE TYPERROR ---
@login_required
def nivel(request):
    # CORREÇÃO: Converte o valor para Decimal para evitar TypeError na multiplicação (Decimal * float)
    INVITE_COMMISSION_PERCENTAGE = Decimal('0.15') # 15%
    # FIM DO NOVO PERCENTUAL
    
    levels = Level.objects.all().order_by('deposit_value')
    user_levels = UserLevel.objects.filter(user=request.user, is_active=True).values_list('level__id', flat=True)
    
    if request.method == 'POST':
        level_id = request.POST.get('level_id')
        level_to_buy = get_object_or_404(Level, id=level_id)

        if level_to_buy.id in user_levels:
            messages.error(request, 'Você já possui este nível.')
            return redirect('nivel')
        
        if request.user.available_balance >= level_to_buy.deposit_value:
            request.user.available_balance -= level_to_buy.deposit_value
            
            # --- ATUALIZAÇÃO IMPORTANTE PARA INICIALIZAR O CAMPO last_daily_gain_date ---
            # Para o novo ciclo de 24h funcionar corretamente a partir da compra:
            UserLevel.objects.create(
                user=request.user, 
                level=level_to_buy, 
                is_active=True,
                # O primeiro ciclo será gerado 24h após a compra.
                # Não definimos last_daily_gain_date aqui para que o primeiro cálculo na tarefa(request) use a purchase_date.
            )
            
            request.user.level_active = True
            request.user.save()
            
            invited_by_user = request.user.invited_by
            if invited_by_user and UserLevel.objects.filter(user=invited_by_user, is_active=True).exists():
                # Calcula a nova comissão de 15%
                commission_amount = level_to_buy.deposit_value * INVITE_COMMISSION_PERCENTAGE
                
                invited_by_user.subsidy_balance += commission_amount
                invited_by_user.available_balance += commission_amount
                invited_by_user.save()
                messages.success(request, f'Parabéns! Você recebeu {commission_amount:.2f} KZ de subsídio por convite de {request.user.phone_number} (15% do investimento).')

            messages.success(request, f'Você comprou o nível {level_to_buy.name} com sucesso! O seu primeiro ganho estará disponível em 24h.')
        else:
            messages.error(request, 'Saldo insuficiente. Por favor, faça um depósito.')
        
        return redirect('nivel')
        
    context = {
        'levels': levels,
        'user_levels': user_levels,
    }
    return render(request, 'nivel.html', context)
# --- FIM DA FUNÇÃO NIVEL ATUALIZADA ---

@login_required
def equipa(request):
    user = request.user

    # 1. Encontra todos os membros da equipe (convidados diretos)
    team_members = CustomUser.objects.filter(invited_by=user).order_by('-date_joined')
    team_count = team_members.count()

    # 2. Obtém todos os Níveis disponíveis
    all_levels = Level.objects.all().order_by('deposit_value')

    # 3. Contabilização por Nível de Investimento
    levels_data = []
    total_investors = 0
    
    # Dicionário para armazenar membros por nível (para exibição no template)
    members_by_level = {} 
    
    # Preenche os dados para cada nível
    for level in all_levels:
        # Filtra membros da equipe que possuem este nível ATIVO
        members_with_level = team_members.filter(userlevel__level=level, userlevel__is_active=True).distinct()
        
        levels_data.append({
            'name': level.name,
            'count': members_with_level.count(),
            'members': members_with_level, 
        })
        members_by_level[level.name] = members_with_level
        total_investors += members_with_level.count()

    # 4. Contabilização de Não Investidores GERAL
    # Membros que NÃO têm NENHUM UserLevel ativo
    non_invested_members = team_members.exclude(userlevel__is_active=True)
    total_non_investors = non_invested_members.count()
    
    # Adiciona a contagem de não investidos na estrutura levels_data para a primeira aba
    levels_data.insert(0, {
        'name': 'Não Investido',
        'count': total_non_investors,
        'members': non_invested_members,
    })

    context = {
        'team_members': team_members, # Membros totais
        'team_count': team_count, # Contagem total de membros
        'invite_link': request.build_absolute_uri(reverse('cadastro')) + f'?invite={user.invite_code}',
        'levels_data': levels_data, # Dados detalhados por nível (para as abas)
        'total_investors': total_investors, # Contagem de investidores
        'total_non_investors': total_non_investors, # Contagem de não investidores
        'subsidy_balance': user.subsidy_balance, # Saldo de Subsídios
    }
    return render(request, 'equipa.html', context)

@login_required
def roleta(request):
    user = request.user
    
    context = {
        'roulette_spins': user.roulette_spins,
    }
    
    return render(request, 'roleta.html', context)

@login_required
@require_POST
def spin_roulette(request):
    user = request.user

    if not user.roulette_spins or user.roulette_spins <= 0:
        return JsonResponse({'success': False, 'message': 'Você não tem giros disponíveis para a roleta.'})

    user.roulette_spins -= 1
    user.save()
    
    try:
        roulette_settings = RouletteSettings.objects.first()
        
        if roulette_settings and roulette_settings.prizes:
            prizes_from_admin = [int(p.strip()) for p in roulette_settings.prizes.split(',')]
            prizes_weighted = []
            for prize in prizes_from_admin:
                if prize <= 1000:
                    prizes_weighted.extend([prize] * 3)
                else:
                    prizes_weighted.append(prize)
            prize = random.choice(prizes_weighted)
        else:
            prizes = [100, 200, 300, 500, 1000, 2000]
            prize = random.choice(prizes)

    except RouletteSettings.DoesNotExist:
        prizes = [100, 200, 300, 500, 1000, 2000]
        prize = random.choice(prizes)

    Roulette.objects.create(user=user, prize=prize, is_approved=True)

    user.subsidy_balance += prize
    user.available_balance += prize
    user.save()

    return JsonResponse({'success': True, 'prize': prize, 'message': f'Parabéns! Você ganhou {prize} KZ.'})

@login_required
def sobre(request):
    try:
        platform_settings = PlatformSettings.objects.first()
        history_text = platform_settings.history_text if platform_settings else 'Histórico da plataforma não disponível.'
    except PlatformSettings.DoesNotExist:
        history_text = 'Histórico da plataforma não disponível.'

    return render(request, 'sobre.html', {'history_text': history_text})

@login_required
def perfil(request):
    bank_details, created = BankDetails.objects.get_or_create(user=request.user)
    user_levels = UserLevel.objects.filter(user=request.user, is_active=True)

    if request.method == 'POST':
        form = BankDetailsForm(request.POST, instance=bank_details)
        password_form = PasswordChangeForm(request.user, request.POST)

        if 'update_bank' in request.POST:
            if form.is_valid():
                form.save()
                messages.success(request, 'Detalhes bancários atualizados com sucesso!')
                return redirect('perfil')
            else:
                messages.error(request, 'Ocorreu um erro ao atualizar os detalhes bancários.')

        if 'change_password' in request.POST:
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Sua senha foi alterada com sucesso!')
                return redirect('perfil')
            else:
                messages.error(request, 'Ocorreu um erro ao alterar a senha. Verifique se a senha antiga está correta e a nova senha é válida.')
    else:
        form = BankDetailsForm(instance=bank_details)
        password_form = PasswordChangeForm(request.user)

    context = {
        'form': form,
        'password_form': password_form,
        'user_levels': user_levels,
    }
    return render(request, 'perfil.html', context)

@login_required
def renda(request):
    user = request.user
    
    active_level = UserLevel.objects.filter(user=user, is_active=True).first()

    approved_deposit_total = Deposit.objects.filter(user=user, is_approved=True).aggregate(Sum('amount'))['amount__sum'] or 0
    
    today = date.today()
    # A linha abaixo foi alterada para calcular o ganho diário com base nos registros da Task.
    daily_income = Task.objects.filter(user=user, completed_at__date=today).aggregate(Sum('earnings'))['earnings__sum'] or 0

    # A linha abaixo foi alterada para corrigir o status para 'Aprovado'
    total_withdrawals = Withdrawal.objects.filter(user=user, status='Aprovado').aggregate(Sum('amount'))['amount__sum'] or 0

    total_income = (Task.objects.filter(user=user).aggregate(Sum('earnings'))['earnings__sum'] or 0) + user.subsidy_balance
    
    context = {
        'user': user,
        'active_level': active_level,
        'approved_deposit_total': approved_deposit_total,
        'daily_income': daily_income,
        'total_withdrawals': total_withdrawals,
        'total_income': total_income,
    }
    return render(request, 'renda.html', context)
    