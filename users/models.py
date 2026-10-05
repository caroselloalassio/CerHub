from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class CustomUser(AbstractUser):
    LEGAL_TYPES = [
        ('PRIVATE', 'Privato'),
        ('BUSINESS', 'Azienda'),
        ('ASSOCIATION', 'Associazione'),
        ('CHURCH', 'Ente Religioso'),
        ('PUBLIC', 'Ente Pubblico'),
    ]
    
    PROFIT_TYPES = [
        ('PROFIT', 'Con scopo di lucro'),
        ('NON_PROFIT', 'Senza scopo di lucro'),
    ]
   
    # Campi base
    legal_type = models.CharField(
        max_length=20, 
        choices=LEGAL_TYPES, 
        default='PRIVATE',
        verbose_name="Tipo Soggetto"
    )
    profit_type = models.CharField(
        max_length=20, 
        choices=PROFIT_TYPES, 
        default='NON_PROFIT',
        verbose_name="Finalità"
    )
    fiscal_code = models.CharField(
        max_length=16, 
        blank=True, 
        null=True,
        verbose_name="Codice Fiscale"
    )
    address = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name="Indirizzo"
    )
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        verbose_name="Telefono"
    )

    # Campi per aziende/enti
    vat_number = models.CharField(
        max_length=11, 
        blank=True, 
        null=True, 
        verbose_name="Partita IVA",
        help_text="11 caratteri per la partita IVA"
    )

    legal_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Denominazione"
    )
    pec = models.EmailField(
        blank=True, 
        null=True, 
        verbose_name="PEC"
    )
    sdi_code = models.CharField(
        max_length=7, 
        blank=True, 
        null=True, 
        verbose_name="Codice SDI"
    )

    # Campi per associazioni
    registration_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="Numero Registrazione"
    )
    statute_date = models.DateField(
        blank=True, 
        null=True, 
        verbose_name="Data Statuto"
    )

    # Campi per enti religiosi
    religious_entity_code = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="Codice Ente Religioso"
    )

    # Consensi GDPR
    privacy_accepted = models.BooleanField(
        "Privacy Accettata",
        default=False,
        help_text="Indica se l'utente ha accettato la privacy policy"
    )
    privacy_acceptance_date = models.DateTimeField(
        "Data Accettazione Privacy",
        null=True,
        blank=True
    )
    privacy_last_update = models.DateTimeField(
        "Ultimo Aggiornamento Privacy",
        null=True,
        blank=True
    )
    
    # Property per verifica tipo utente
    @property
    def is_business(self):
        """Verifica se l'utente è un'azienda"""
        return self.legal_type == 'BUSINESS'
    
    @property
    def is_private(self):
        """Verifica se l'utente è un privato"""
        return self.legal_type == 'PRIVATE'
    
    @property
    def is_association(self):
        """Verifica se l'utente è un'associazione"""
        return self.legal_type == 'ASSOCIATION'
    
    @property
    def is_church(self):
        """Verifica se l'utente è un ente religioso"""
        return self.legal_type == 'CHURCH'
    
    @property
    def is_public(self):
        """Verifica se l'utente è un ente pubblico"""
        return self.legal_type == 'PUBLIC'
    
    @property
    def requires_vat(self):
        """Verifica se l'utente richiede partita IVA"""
        return self.legal_type in ['BUSINESS', 'ASSOCIATION', 'CHURCH', 'PUBLIC']
    
    @property
    def requires_pec(self):
        """Verifica se l'utente richiede PEC"""
        return self.legal_type in ['BUSINESS', 'ASSOCIATION', 'PUBLIC']
    
    def accept_privacy(self):
        """
        Registra l'accettazione della privacy da parte dell'utente
        """
        now = timezone.now()
        self.privacy_accepted = True
        self.privacy_acceptance_date = now
        self.privacy_last_update = now
        self.save()
    def update_privacy(self):
        """
        Registra un aggiornamento della privacy
        """
        self.last_privacy_update = timezone.now()
        self.save(update_fields=['last_privacy_update'])

    def clean(self):
        super().clean()
        # Imposta automaticamente NON_PROFIT per soggetti privati
        if self.legal_type == 'PRIVATE':
            self.profit_type = 'NON_PROFIT'

        # Validazioni specifiche per tipo
        if self.legal_type == 'PRIVATE':
            if not all([self.first_name, self.last_name]):
                raise ValidationError('Nome e cognome sono obbligatori per gli utenti privati.')
        elif self.legal_type in ['BUSINESS', 'ASSOCIATION']:
            if not all([self.vat_number, self.legal_name, self.pec]):
                raise ValidationError('Partita IVA, denominazione e PEC sono obbligatori per aziende e associazioni.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Utente"
        verbose_name_plural = "Utenti"
        ordering = ['username']
        permissions = [
            ("can_view_all_users", "Può vedere tutti gli utenti"),
            ("can_manage_users", "Può gestire gli utenti"),
            ("can_approve_users", "Può approvare gli utenti"),
        ]
        indexes = [
            models.Index(fields=['legal_type']),
            models.Index(fields=['fiscal_code']),
            models.Index(fields=['vat_number']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(legal_type__in=['PRIVATE', 'BUSINESS', 'ASSOCIATION', 'CHURCH', 'PUBLIC']),
                name='valid_legal_type'
            ),
            models.CheckConstraint(
                condition=models.Q(profit_type__in=['PROFIT', 'NON_PROFIT']),
                name='valid_profit_type'
            ),
        ]

    def __str__(self):
        if self.legal_name:
            return f"{self.legal_name} ({self.get_legal_type_display()})"
        return f"{self.username} ({self.get_legal_type_display()})"