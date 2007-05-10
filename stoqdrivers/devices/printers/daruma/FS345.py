# -*- Mode: Python; coding: iso-8859-1 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Stoqdrivers
## Copyright (C) 2005-2007 Async Open Source <http://www.async.com.br>
## All rights reserved
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307,
## USA.
##
## Author(s):   Johan Dahlin     <jdahlin@async.com.br>
##              Henrique Romano  <henrique@async.com.br>
##
"""
Daruma FS345 driver
"""
import datetime
from decimal import Decimal
import time

from kiwi.log import Logger
from kiwi.python import Settable
from zope.interface import implements

from stoqdrivers import abicomp
from stoqdrivers.devices.serialbase import SerialBase
from stoqdrivers.devices.interfaces import ICouponPrinter
from stoqdrivers.devices.printers.capabilities import Capability
from stoqdrivers.devices.printers.base import BaseDriverConstants
from stoqdrivers.enum import PaymentMethodType, TaxType, UnitType
from stoqdrivers.exceptions import (DriverError, PendingReduceZ,
                                    HardwareFailure,
                                    AuthenticationFailure, CommError,
                                    PendingReadX, CouponNotOpenError,
                                    OutofPaperError, PrinterOfflineError,
                                    CouponOpenError, CancelItemError,
                                    CloseCouponError)
from stoqdrivers.translation import stoqdrivers_gettext

abicomp.register_codec()

_ = lambda msg: stoqdrivers_gettext(msg)

log = Logger('stoqdrivers.daruma')

CMD_STATUS = '\x1d\xff'

CMD_SET_OWNER = 190
# [ESC] 191 Grava��o da indica��o de mudan�a de moeda
# [ESC] 192 Interven��o T�cnica
CMD_GET_MODEL = 195
CMD_GET_FIRMWARE = 199
CMD_OPEN_COUPON = 200
CMD_IDENTIFY_CUSTOMER = 201
CMD_ADD_ITEM_1L6D = 202
CMD_ADD_ITEM_2L6D = 203
CMD_ADD_ITEM_3L6D = 204
CMD_CANCEL_ITEM = 205
# [ESC] 206 Cancelamento de Documento
CMD_CANCEL_COUPON = 206
CMD_GET_X = 207
CMD_REDUCE_Z = 208
CMD_READ_MEMORY = 209
# [ESC] 210 Emiss�o de Cupom Adicional
# [ESC] 211 Abertura de Relat�rio Gerencial (Leitura X)
# [ESC] 212 Fechamento de Relat�rio Gerencial (Leitura X)
# [ESC] 213 Linha de texto de Relat�rio Gerencial (Leitura X)
CMD_ADD_ITEM_1L13D = 214
CMD_ADD_ITEM_2L13D = 215
CMD_ADD_ITEM_3L13D = 216
CMD_OPEN_VOUCHER = 217
CMD_DESCRIBE_MESSAGES = 218
# [ESC] 219 Abertura de Comprovante N�o Fiscal Vinculado
# [ESC] 220 Carga de al�quota de imposto
CMD_LAST_RECORD = 221
# [ESC] 223 Descri��o de produto em 3 linhas com c�digo de 13 d�gitos
#           (Formato fixo p/ Quantidade 5,3)
CMD_ADD_ITEM_3L13D53U = 223
# [ESC] 225 Descri��o de produto com pre�o unit�rio com 3 decimais
# [ESC] 226 Cria��o de Comprovante N�o Fiscal (Vinculado ou N�o)
# [ESC] 227 Subtotaliza��o de Cupom Fiscal
# [ESC] 228 Configura��o da IF
CMD_GET_CONFIGURATION = 229
# [ESC] 230 Leitura do rel�gio interno da impressora
CMD_GET_TAX_CODES = 231
# [ESC] 232 Leitura do clich� do propriet�rio
# [ESC] 234 Retransmiss�o de mensagens da IF
CMD_GET_IDENTIFIER = 236
# [ESC] 238 Leitura das mensagens personalizadas
CMD_GET_DOCUMENT_STATUS = 239
CMD_GET_FISCAL_REGISTRIES = 240
CMD_TOTALIZE_COUPON = 241
CMD_DESCRIBE_PAYMENT_FORM = 242
CMD_CLOSE_COUPON = 243
CMD_GET_REGISTRIES = 244
CMD_GET_TOTALIZERS = 244
# [ESC] 246 Leitura Hor�ria
# [ESC] 247 Descri��o Estendida
# [ESC] 248 Estorno de forma de pagamento
CMD_GET_DATES = 250
# [ESC] 251 Leitura das informa��es cadastrais do usu�rio
# [ESC] V   Controle de hor�rio de ver�o

CASH_IN_TYPE = 'B'
CASH_OUT_TYPE = 'A'

def isbitset(value, bit):
    # BCD crap
    return (int(value, 16) >> bit) & 1 == 1

def ifset(value, bit, false='', true=''):
    if not isbitset(value, bit):
        return false
    else:
        return true

class FS345Constants(BaseDriverConstants):
    _constants = {
        UnitType.WEIGHT:      'Kg',
        UnitType.METERS:      'm ',
        UnitType.LITERS:      'Lt',
        UnitType.EMPTY:       '  ',
        PaymentMethodType.MONEY:         'A',
        PaymentMethodType.CHECK:        'B'
        }

    _tax_constants = [
        # These definitions can be found on Page 60
        (TaxType.SUBSTITUTION,   'Fb', None),
        (TaxType.EXEMPTION,      'Ib', None),
        (TaxType.NONE,           'Nb', None),

        # Reducao Z output
        (TaxType.CUSTOM,         'Ta', Decimal(18)),
        (TaxType.CUSTOM,         'Tb', Decimal(12)),
        (TaxType.CUSTOM,         'Tc', Decimal(5)),
        ]

class FS345(SerialBase):
    log_domain = 'fs345'

    implements(ICouponPrinter)

    model_name = "Daruma FS 345"
    coupon_printer_charset = "abicomp"

    def __init__(self, port, consts=None):
        self._consts = consts or FS345Constants
        SerialBase.__init__(self, port)
        self._reset()

    def _reset(self):
        self._customer_name = u""
        self._customer_document = u""
        self._customer_address = u""

    def send_command(self, command, extra=''):
        raw = chr(command) + extra
        retval = self.writeline(raw)
        if retval.startswith(':E'):
            self.handle_error(retval, raw)
        return retval[1:]

    # Status
    def _get_status(self):
        self.write(CMD_STATUS)
        return self.readline()

    def status_check(self, S, byte, bit):
        return isbitset(S[byte], bit)

    def _check_status(self, verbose=False):
        status = self._get_status()
        if status[0] != ':':
            raise HardwareFailure('Broken status reply')

        if verbose:
            print '== STATUS =='

            # Codes found on page 57-59
            print 'Raw status code:', status
            print 'Cashier drawer is', ifset(status[1], 3, 'closed', 'open')

        if self.needs_reduce_z():
            raise PendingReduceZ(_('Pending Reduce Z'))
        if self.status_check(status, 1, 2):
            raise HardwareFailure(_('Mechanical failure'))
        if not self.status_check(status, 1, 1):
            raise AuthenticationFailure(_('Not properly authenticated'))
        if self.status_check(status, 1, 0):
            raise OutofPaperError(_('No paper'))
        if self.status_check(status, 2, 3):
            raise PrinterOfflineError(_("Offline"))
        if not self.status_check(status, 2, 2):
             raise CommError(_("Peripheral is not connected to AUX"))
        if self.status_check(status, 2, 0):
            log.info('Almost out of paper')

        if verbose:
            S3 = status[3]
            print ifset(S3, 3, 'Maintenance', 'Operational'), 'mode'
            print 'Authentication', ifset(S3, 2, 'disabled', 'enabled')
            print 'Guillotine', ifset(S3, 1, 'disabled', 'enabled')
            print 'Auto close CF?', ifset(S3, 0, 'no', 'yes')

        if self.needs_read_x(status):
            raise PendingReadX(_("readX is not emitted yet"))

        return status

    def needs_reduce_z(self, status=None):
        if not status:
            status = self._get_status()
        return self.status_check(status, 2, 1)

    def needs_read_x(self, status=None):
        if not status:
            status = self._get_status()

        return not self.status_check(status, 6, 2)

    # Error handling

    def handle_error(self, error_value, raw):
        error = int(error_value[2:])
        # Page 61-62
        if error == 39:
            raise DriverError('Bad parameters: %r'  % raw)
        elif error == 10:
            raise CouponOpenError(_("Document is already open"))
        elif error == 11:
            raise CouponNotOpenError(_("Coupon is not open"))
        elif error == 12:
            raise CouponNotOpenError(_("There's no open document to cancel"))
        elif error == 15:
            raise CancelItemError(_("There is no such item in "
                                    "the coupon"))
        elif error == 16:
            raise DriverError("Bad discount/markup parameter")
        elif error == 21:
            log.warning(_('No paper'))
        elif error == 22:
            raise DriverError(
                "Reduce Z was already sent today, try again tomorrow")
        elif error == 23:
            raise DriverError("Bad description: %r" % raw)
        elif error == 24:
            raise DriverError("Bad unit specified: %r" % raw)
        elif error == 42:
            raise DriverError("Read X has not been sent yet")
        elif error == 45:
            raise DriverError("Bad numeric string")
        else:
            raise DriverError("Unhandled error: %d" % error)

    # Information / debugging

    def show_status(self):
        self._check_status(verbose=True)

    def show_information(self):
        print 'Model:', self.send_command(CMD_GET_MODEL, debug=False)
        print 'Firmware:', self.send_command(CMD_GET_FIRMWARE, debug=False)
        data = self.send_command(CMD_LAST_RECORD, debug=False)

        tt = time.strptime(data[:12], '%d%m%y%H%M%S')
        print 'Last record:', time.strftime('%c', tt)
        print 'Configuration:', self.send_command(CMD_GET_CONFIGURATION,
                                               debug=False)

    def show_document_status(self):
        print '== DOCUMENT STATUS =='
        value = self.send_command(CMD_GET_DOCUMENT_STATUS, debug=False)
        assert value[:2] == '\x1b' + chr(CMD_GET_DOCUMENT_STATUS)
        assert len(value) == 59
        print 'ECF:', value[2:6]
        document_type = value[6]
        if document_type == '2':
            print 'No open coupon'
        elif document_type == '1':
            print 'Document is a coupon (%s)' % value[7:12]
        else:
            print 'Document type:', value[6]

        tt = time.strptime(value[13:27], '%H%M%S%d%m%Y')
        print 'Current date/time:', time.strftime('%c', tt)

        print 'Sum', int(value[27:41]) / 100.0
        print 'GT atual', value[41:59]

    def _get_fiscal_registers(self):
        value = self.send_command(CMD_GET_FISCAL_REGISTRIES)
        assert value[:2] == '\x1b' + chr(CMD_GET_FISCAL_REGISTRIES)
        return value[2:]

    def _get_registers(self):
        value = self.send_command(CMD_GET_REGISTRIES)
        assert value[:2] == '\x1b' + chr(CMD_GET_REGISTRIES)
        return value[2:]

    # High level commands
    def _verify_coupon_open(self):
        if not self.status_check(self._get_status(), 4, 2):
            raise CouponNotOpenError(_("Coupon is not open"))

    def _is_open(self, status):
        return self.status_check(status, 4, 2)

    # Helper commands

    def _get_totalizers(self):
        return self.send_command(CMD_GET_TOTALIZERS)

    def _get_coupon_number(self):
        return int(self._get_totalizers()[8:14])

    def _add_payment(self, payment_method, value, description='',
                     custom_pm=''):
        if not custom_pm:
            pm = self._consts.get_value(payment_method)
        else:
            pm = custom_pm
        rv = self.send_command(CMD_DESCRIBE_PAYMENT_FORM,
                               '%c%012d%s\xff' % (pm, int(float(value) * 1e2),
                                                  description[:48]))
        return float(rv) / 1e2

    def _add_voucher(self, type, value):
        data = "%s1%s%012d\xff" % (type, "0" * 12, # padding
                                   int(float(value) * 1e2))
        self.send_command(CMD_OPEN_VOUCHER, data)

    def _get_taxes(self):
        fiscal_registries = self._get_fiscal_registers()
        tax_codes = self.send_command(CMD_GET_TAX_CODES)[1:]

        taxes = []
        for i in range(14):
            if tax_codes[i*5] in 'ABCDEFGHIJKLMNOP':
                reg = tax_codes[i*5+1:i*5+5]
                if reg == '////':
                    continue
                reg = reg.replace('.', '')
            else:
                reg = 'ISS'
            sold = fiscal_registries[87+(i*14):101+(i*14)]
            taxes.append((reg, Decimal(sold)/100))

        taxes.append(('DESC', Decimal(fiscal_registries[19:32]) / 100))
        taxes.append(('CANC', Decimal(fiscal_registries[33:46]) / 100))
        taxes.append(('I', Decimal(fiscal_registries[47:60]) / 100))
        taxes.append(('N', Decimal(fiscal_registries[61:74]) / 100))
        taxes.append(('F', Decimal(fiscal_registries[75:88]) / 100))
        return taxes

    def _generate_sintegra(self):
        registries = self._get_registers()
        fiscal_registries = self._get_fiscal_registers()

        taxes = self._get_taxes()
        total_sold = sum(value for _, value in taxes)

        old_total = Decimal(fiscal_registries[:18]) / 100
        cancelled = Decimal(fiscal_registries[33:46]) / 100
        period_total = total_sold + cancelled

        dates = self.send_command(CMD_GET_DATES)
        if dates[:6] == '000000':
            opening_date = datetime.date.today()
        else:
            d, m, y = map(int, [dates[:2], dates[2:4], dates[4:6]])
            opening_date = datetime.date(2000+y, m, d)

        identifier = self.send_command(CMD_GET_IDENTIFIER)
        return Settable(
             opening_date=opening_date,
             serial=identifier[1:9],
             serial_id=int(identifier[13:17]),
             coupon_start=int(registries[:6]),
             coupon_end=int(registries[7:12]),
             cro=int(registries[35:38]),
             crz=int(registries[39:42]),
             period_total=period_total,
             total=period_total + old_total,
             taxes=taxes)

    #
    # API implementation
    #

    def coupon_identify_customer(self, customer, address, document):
        self._customer_name = customer
        self._customer_document = document
        self._customer_address = address

    def coupon_open(self):
        status = self._check_status()
        if self._is_open(status):
            raise CouponOpenError(_("Coupon already open"))
        self.send_command(CMD_OPEN_COUPON)

    def coupon_add_item(self, code, description, price, taxcode,
                        quantity=Decimal("1.0"), unit=UnitType.EMPTY,
                        discount=Decimal("0.0"),
                        surcharge=Decimal("0.0"), unit_desc=""):
        if surcharge:
            d = 1
            E = surcharge
        else:
            d = 0
            E = discount

        if unit == UnitType.CUSTOM:
            unit = unit_desc
        else:
            unit = self._consts.get_value(unit)
        data = '%2s%13s%d%04d%010d%08d%s%s\xff' % (taxcode, code[:13], d,
                                                   int(float(E) * 1e2),
                                                   int(float(price) * 1e3),
                                                   int(float(quantity) * 1e3),
                                                   unit, description[:174])
        value = self.send_command(CMD_ADD_ITEM_3L13D53U, data)
        return int(value[1:4])

    def coupon_cancel_item(self, item_id):
        self.send_command(CMD_CANCEL_ITEM, "%03d" % item_id)

    def coupon_add_payment(self, payment_method, value, description='',
                           custom_pm=''):
        self._check_status()
        self._verify_coupon_open()
        return self._add_payment(payment_method, value, description,
                                 custom_pm)

    def coupon_cancel(self):
        # If we need reduce Z don't verify that the coupon is open, instead
        # just cancel the coupon. This avoids a race when you forgot
        # to close a coupon and reduce Z at the same time.
        if not self.needs_reduce_z():
            self._check_status()
        self.send_command(CMD_CANCEL_COUPON)

    def coupon_totalize(self, discount=Decimal("0.0"), surcharge=Decimal("0.0"),
                        taxcode=TaxType.NONE):
        self._check_status()
        self._verify_coupon_open()
        if surcharge:
            value = surcharge
            if taxcode == TaxType.ICMS:
                mode = 2
            else:
                raise ValueError("tax_code must be TaxType.ICMS")
        elif discount:
            value = discount
            mode = 0
        else:
            mode = 0
            value = Decimal("0")
        # Page 33
        data = '%d%04d00000000' % (mode, int(value * Decimal("1e2")))
        rv = self.send_command(CMD_TOTALIZE_COUPON, data)
        return Decimal(rv) / Decimal("1e2")

    def coupon_close(self, message=''):
        self._check_status()
        self._verify_coupon_open()

        empty = " " *42

        if (self._customer_name or self._customer_address or
            self._customer_document):
            self.send_command(CMD_IDENTIFY_CUSTOMER,
                              (("% 42s" % self._customer_name) + empty +
                               ("% 42s" % self._customer_address) + empty +
                               ("% 42s" % self._customer_document) + empty))
        LINE_LEN = 48
        msg_len = len(message)
        if msg_len > LINE_LEN:
            l = []
            for i in range(0, msg_len, LINE_LEN):
                l.append(message[i:i+LINE_LEN])
            message = '\n'.join(l)
        try:
            self.send_command(CMD_CLOSE_COUPON, message + '\xff')
        except DriverError:
            raise CloseCouponError(_("It is not possible to close the "
                                     "coupon"))
        self._reset()
        return self._get_coupon_number()

    def summarize(self):
        self.send_command(CMD_GET_X)

    def close_till(self):
        status = self._get_status()
        if self._is_open(status):
            self.send_command(CMD_CANCEL_COUPON)

        data = self._generate_sintegra()

        date = time.strftime('%d%m%y%H%M%S', time.localtime())
        self.send_command(CMD_REDUCE_Z, date)

        return data

    def till_add_cash(self, value):
        self._add_voucher(CASH_IN_TYPE, value)
        self._add_payment(PaymentMethodType.MONEY, value, '')

    def till_remove_cash(self, value):
        self._add_voucher(CASH_OUT_TYPE, value)

    def till_read_memory(self, start, end):
        # Page 39
        self.send_command(CMD_READ_MEMORY, 's%s%s' % (start.strftime('%d%m%y'),
                                                      end.strftime('%d%m%y')))

    def get_capabilities(self):
        return dict(item_code=Capability(max_len=13),
                    item_id=Capability(digits=3),
                    items_quantity=Capability(min_size=1, digits=5, decimals=3),
                    item_price=Capability(min_size=0, digits=7, decimals=3),
                    item_description=Capability(max_len=173),
                    payment_value=Capability(digits=10, decimals=2),
                    promotional_message=Capability(max_len=384),
                    payment_description=Capability(max_len=48),
                    customer_name=Capability(max_len=42),
                    customer_id=Capability(max_len=42),
                    customer_address=Capability(max_len=42),
                    remove_cash_value=Capability(min_size=1, digits=10,
                                                 decimals=2),
                    add_cash_value=Capability(min_size=1, digits=10,
                                              decimals=2))

    def get_constants(self):
        return self._consts

