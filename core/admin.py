from django.contrib import admin
from django.utils.safestring import mark_safe # Importação necessária para renderizar HTML no Admin
from .models import (
    CustomUser, PlatformSettings, Level, BankDetails, Deposit, 
    Withdrawal, Task, Roulette, RouletteSettings, UserLevel, PlatformBankDetails
)

# ---

# Registrando os modelos com classes ModelAdmin personalizadas

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'available_balance', 'subsidy_balance', 'is_staff', 'is_active', 'date_joined', 'roulette_spins')
    search_fields = ('phone_number', 'invite_code')
    list_filter = ('is_staff', 'is_active', 'level_active')

@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    # Adicionado 'app_download_link' se você atualizou o models.py para exibir no admin
    list_display = ('id', 'whatsapp_link', 'app_download_link', 'history_text', 'deposit_instruction', 'withdrawal_instruction') 
    search_fields = ('whatsapp_link',)

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'deposit_value', 'daily_gain', 'monthly_gain', 'cycle_days')
    search_fields = ('name',)

@admin.register(BankDetails)
class BankDetailsAdmin(admin.ModelAdmin):
    list_display = ('user', 'bank_name', 'IBAN', 'account_holder_name')
    search_fields = ('user__phone_number', 'bank_name', 'account_holder_name')

@admin.register(PlatformBankDetails)
class PlatformBankDetailsAdmin(admin.ModelAdmin):
    list_display = ('bank_name', 'account_holder_name')
    search_fields = ('bank_name', 'account_holder_name')

@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    # Adicionamos 'proof_link' para mostrar o link na lista de depósitos
    list_display = ('user', 'amount', 'is_approved', 'created_at', 'proof_link') 
    search_fields = ('user__phone_number',)
    list_filter = ('is_approved',)
    
    # Campos que serão apenas de leitura na página de edição/criação
    readonly_fields = ('current_proof_display',)

    # Método para criar o link do comprovativo na LISTA de depósitos
    def proof_link(self, obj):
        if obj.proof_of_payment:
            # obj.proof_of_payment.url usa o Cloudinary Storage para obter o URL completo.
            return mark_safe(f'<a href="{obj.proof_of_payment.url}" target="_blank">Ver Comprovativo</a>')
        return "Nenhum"
        
    proof_link.short_description = 'Comprovativo'

    # Método para exibir a imagem/link na PÁGINA DE EDIÇÃO/MODIFICAÇÃO
    def current_proof_display(self, obj):
        if obj.proof_of_payment:
            # Exibe a imagem diretamente e fornece um link para visualização
            return mark_safe(f'''
                <a href="{obj.proof_of_payment.url}" target="_blank">Ver Imagem em Tamanho Real</a><br/>
                <img src="{obj.proof_of_payment.url}" style="max-width:300px; height:auto; margin-top: 10px;" />
            ''')
        return "Nenhum Comprovativo Carregado"
    
    current_proof_display.short_description = 'Comprovativo Atual'

@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    # --- ALTERAÇÃO AQUI: Adicionado 'user_iban' e 'account_details' ---
    list_display = ('user', 'amount', 'status', 'user_iban', 'account_details', 'created_at')
    # --- FIM ALTERAÇÃO ---
    search_fields = ('user__phone_number',)
    list_filter = ('status',)
    
    # --- NOVO MÉTODO PARA PEGAR IBAN ---
    def user_iban(self, obj):
        try:
            # Tenta obter os detalhes bancários do usuário
            bank_details = BankDetails.objects.get(user=obj.user)
            return bank_details.IBAN
        except BankDetails.DoesNotExist:
            return "N/A (Adicionar)"
            
    user_iban.short_description = 'IBAN do Cliente'
    # --- FIM NOVO MÉTODO ---
    
    # --- NOVO MÉTODO PARA PEGAR DETALHES DA CONTA (Nome/Banco) ---
    def account_details(self, obj):
        try:
            bank_details = BankDetails.objects.get(user=obj.user)
            return f"{bank_details.account_holder_name} ({bank_details.bank_name})"
        except BankDetails.DoesNotExist:
            return "N/A (Adicionar)"

    account_details.short_description = 'Nome/Banco'
    # --- FIM NOVO MÉTODO ---

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('user', 'earnings', 'completed_at')
    search_fields = ('user__phone_number',)

@admin.register(Roulette)
class RouletteAdmin(admin.ModelAdmin):
    list_display = ('user', 'prize', 'is_approved', 'spin_date')
    search_fields = ('user__phone_number',)
    list_filter = ('is_approved',)

@admin.register(RouletteSettings)
class RouletteSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'prizes')

@admin.register(UserLevel)
class UserLevelAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'purchase_date', 'is_active')
    search_fields = ('user__phone_number', 'level__name')
    list_filter = ('is_active',)

# ---
