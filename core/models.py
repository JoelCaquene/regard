from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.db.models import Sum # Import necessário para a propriedade total_withdrawn
import uuid
import os

# ---

class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('O número de telefone deve ser fornecido')
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(phone_number, password, **extra_fields)

# ---

class CustomUser(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(max_length=20, unique=True, verbose_name="Número de Telefone")
    full_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nome Completo")
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    invite_code = models.CharField(max_length=8, unique=True, blank=True, null=True)
    invited_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Convidado por")
    available_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Saldo Disponível")
    subsidy_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Saldo de Subsídios")
    level_active = models.BooleanField(default=False, verbose_name="Nível Ativo")
    roulette_spins = models.IntegerField(default=0, verbose_name="Giros da Roleta")

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.phone_number

    def save(self, *args, **kwargs):
        if not self.invite_code:
            while True:
                new_invite_code = uuid.uuid4().hex[:8]
                if not CustomUser.objects.filter(invite_code=new_invite_code).exists():
                    self.invite_code = new_invite_code
                    break
        super().save(*args, **kwargs)
        
    # --- PROPRIEDADES ADICIONADAS PARA O PERFIL ---
    @property
    def active_level(self):
        """
        Retorna o objeto Level ativo do usuário. 
        Necessário para a exibição de {{ user.active_level.name }} no template.
        """
        # Acessa o UserLevel ativo, que tem uma FK para o Level
        active_user_level = self.userlevel_set.filter(is_active=True).first()
        
        # Se houver um nível ativo, retorna o objeto Level. Se não, retorna None.
        return active_user_level.level if active_user_level else None

    @property
    def total_withdrawn(self):
        """
        Calcula e retorna o total de saques aprovados do usuário.
        Necessário para a exibição de {{ user.total_withdrawn }} no template.
        """
        # Calcula a soma dos saques com status 'Aprovado' (assumindo o status que usa)
        total = Withdrawal.objects.filter(user=self, status='Aprovado').aggregate(
            Sum('amount')
        )['amount__sum'] or 0.00
        return total
    # --- FIM DAS PROPRIEDADES ADICIONADAS ---

# ---

class PlatformSettings(models.Model):
    whatsapp_link = models.URLField(
        verbose_name="Link do grupo de apoio do WhatsApp",
        help_text="O link para o grupo de WhatsApp que aparecerá no botão de apoio."
    )
    app_download_link = models.URLField(
        max_length=500,
        default='https://seulinkdedownload.com', # Placeholder. Configure o link real no Admin.
        verbose_name='Link de Download do App',
        help_text="URL completa para o arquivo do aplicativo (APK, loja, etc.)."
    )
    history_text = models.TextField(
        verbose_name="Texto da página 'Sobre'",
        help_text="O histórico da plataforma."
    )
    deposit_instruction = models.TextField(
        verbose_name="Texto de instrução para depósito",
        help_text="Texto que orienta o usuário sobre como fazer o depósito."
    )
    withdrawal_instruction = models.TextField(
        verbose_name="Texto de instrução para saque",
        help_text="Texto que explica a taxa, valor mínimo e horário de saque."
    )
    
    class Meta:
        verbose_name = "Configuração da Plataforma"
        verbose_name_plural = "Configurações da Plataforma"

    def __str__(self):
        return "Configurações da Plataforma"

# ---

class PlatformBankDetails(models.Model):
    bank_name = models.CharField(max_length=100, verbose_name="Nome do Banco")
    IBAN = models.CharField(max_length=50, verbose_name="IBAN")
    account_holder_name = models.CharField(max_length=100, verbose_name="Nome do Titular")

    class Meta:
        verbose_name = "Detalhe Bancário da Plataforma"
        verbose_name_plural = "Detalhes Bancários da Plataforma"
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_holder_name}"

# ---

class BankDetails(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, verbose_name="Usuário")
    bank_name = models.CharField(max_length=100, verbose_name="Nome do Banco")
    IBAN = models.CharField(max_length=50, verbose_name="IBAN")
    account_holder_name = models.CharField(max_length=100, verbose_name="Nome do Titular")
    
    class Meta:
        verbose_name = "Detalhe Bancário do Usuário"
        verbose_name_plural = "Detalhes Bancários do Usuário"

    def __str__(self):
        return f"Detalhes Bancários de {self.user.phone_number}"

# ---

class Deposit(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Usuário")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")
    proof_of_payment = models.ImageField(upload_to='deposit_proofs/', verbose_name="Comprovativo")
    is_approved = models.BooleanField(default=False, verbose_name="Aprovado")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    
    class Meta:
        verbose_name = "Depósito"
        verbose_name_plural = "Depósitos"

    def __str__(self):
        return f"Depósito de {self.amount} por {self.user.phone_number}"

# ---

class Withdrawal(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Usuário")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")
    status = models.CharField(max_length=20, default='Pending', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    
    class Meta:
        verbose_name = "Saque"
        verbose_name_plural = "Saques"

    def __str__(self):
        return f"Saque de {self.amount} por {self.user.phone_number} ({self.status})"

# ---

class Level(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Nome do Nível")
    deposit_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor de Depósito")
    daily_gain = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ganho Diário")
    monthly_gain = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ganho Mensal")
    cycle_days = models.IntegerField(verbose_name="Ciclo (dias)")
    image = models.ImageField(upload_to='level_images/', verbose_name="Imagem")

    class Meta:
        verbose_name = "Nível"
        verbose_name_plural = "Níveis"

    def __str__(self):
        return self.name

# ---

class UserLevel(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Usuário")
    level = models.ForeignKey(Level, on_delete=models.CASCADE, verbose_name="Nível")
    purchase_date = models.DateTimeField(auto_now_add=True, verbose_name="Data da Compra")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    
    # --- NOVO CAMPO ADICIONADO PARA O CICLO DE 24 HORAS ---
    last_daily_gain_date = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Data do Último Ganho Diário",
        help_text="O tempo em que o último ganho de 24 horas foi aplicado. Nulo na primeira compra."
    )
    # --- FIM NOVO CAMPO ---

    class Meta:
        verbose_name = "Nível do Usuário"
        verbose_name_plural = "Níveis dos Usuários"

    def __str__(self):
        return f"{self.user.phone_number} - {self.level.name}"

# ---
# --- NOVO MODELO PARA DEFINIR AS TAREFAS ---
class TaskDefinition(models.Model):
    """
    Define o que é uma tarefa, seu valor de ganho, e se ela é diária.
    """
    name = models.CharField(max_length=100, verbose_name="Nome da Tarefa")
    description = models.TextField(verbose_name="Descrição")
    base_earnings = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Ganho Base"
    )
    is_daily = models.BooleanField(
        default=True, 
        verbose_name="É Diária?",
        help_text="Se marcado, o usuário só pode completar esta tarefa uma vez por dia."
    )
    # Relação opcional: Se a tarefa requer um nível mínimo (e.g., VIP 1)
    required_level = models.ForeignKey(
        Level, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Nível Requerido"
    )

    class Meta:
        verbose_name = "Definição de Tarefa"
        verbose_name_plural = "Definições de Tarefas"

    def __str__(self):
        return self.name
# --- FIM NOVO MODELO ---


# --- MODELO TASK ATUALIZADO ---
class Task(models.Model):
    """
    Registra a conclusão de uma tarefa por um usuário, ligada a uma definição.
    Essa ligação é crucial para a lógica regressiva/diária.
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Usuário")
    # Agora a tarefa completeda se relaciona com uma definição (TaskDefinition)
    task_definition = models.ForeignKey(
        TaskDefinition, 
        on_delete=models.PROTECT, # Garante que a definição não seja apagada se houver registros
        verbose_name="Definição da Tarefa"
    )
    # Os ganhos podem ser registrados aqui (para auditoria, mesmo que sejam baseados na definição)
    earnings = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ganhos Registrados") 
    completed_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Conclusão")

    class Meta:
        verbose_name = "Tarefa Concluída"
        verbose_name_plural = "Tarefas Concluídas"

    def __str__(self):
        return f"Conclusão de '{self.task_definition.name}' por {self.user.phone_number}"
# --- FIM MODELO TASK ATUALIZADO ---

# ---

class Roulette(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Usuário")
    prize = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prêmio")
    spin_date = models.DateTimeField(auto_now_add=True, verbose_name="Data da Rodada")
    is_approved = models.BooleanField(default=False, verbose_name="Aprovado")

    class Meta:
        verbose_name = "Roleta"
        verbose_name_plural = "Roletas"

    def __str__(self):
        return f"Roleta de {self.user.phone_number} - Prêmio: {self.prize}"

# ---

class RouletteSettings(models.Model):
    prizes = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Prêmios da Roleta",
        help_text="Uma lista de prêmios separados por vírgula. Ex: 100,200,500,1000"
    )

    class Meta:
        verbose_name = "Configuração da Roleta"
        verbose_name_plural = "Configurações da Roleta"

    def __str__(self):
        return "Configurações da Roleta"
        