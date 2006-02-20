# -*- Mode: Python; coding: iso-8859-1 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Stoqdrivers
## Copyright (C) 2005 Async Open Source <http://www.async.com.br>
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
## Author(s):   Johan Dahlin                <jdahlin@async.com.br>
##              Evandro Vale Miquelito      <evandro@async.com.br>
##              Henrique Romano             <henrique@async.com.br>
##
##
"""
stoqdrivers/devices/printers/interface.py:

    Printer Driver API
"""

from zope.interface import Interface, Attribute

class IPrinter(Interface):
    model_name = Attribute("The name of the printer that the driver "
                           "implements")

class ICouponPrinter(IPrinter):
    """ Describes coupon related tasks for a printer.

    Workflow

                                    --<--                     --<--
                                   |     |                   |     |
    [identify_customer] -> open -> add_item -> totalize -> add_payment -> close
    """

    coupon_printer_charset = Attribute("The charset name which the "
                                       "coupon printer uses.")

    #
    # Common API
    #

    def identify_customer(customer, address, document):
        """ Identify the customer.  This method doesn't have mandatory
        execution (you can identify the customer only if you like), but when
        executed it must be called before calling any method.

        @param customer:
        @type customer:   str

        @param address:
        @type address:    str

        @param document:
        @type document:   str
        """

    def coupon_open():
        """ This needs to be called before anything else (except
        identify_customer())
        """

    def coupon_add_item(code, quantity, price, unit, description, taxcode,
                        discount, charge, unit_desc=''):
        """ Adds an item to the coupon.

        @param code:      item code identifier
        @type  code:      str

        @param quantity:  quantity
        @type  quantity:  Decimal

        @param price:     price
        @type  price:     Decimal

        @param unit:      constant to describe the unit
        @type unit:       integer constant one of: UNIT_LITERS, UNIT_EMPTY,
                          UNIT_METERS, UNIT_WEIGHT, UNIT_CUSTOM.

        @param description:  description of product
        @type  desription: str

        @param taxcode:   constant to descrive the tax
        @type  taxcode:   integer constant one of: TAX_NONE, TAX_SUBSTITUTION,
                          TAX_EXEMPTION

        @param discount:  discount in %
        @type  discount   Decimal between 0-100

        @param charge:    charge in %
        @type  charge     Decimal between 0-100

        @param unit_desc: A 2-byte string representing the unit that applies to
                          the product.
        @type unit_desc:  str

        @rtype:           Decimal
        @returns          identifier of added item
        """

    def coupon_cancel_item(item_id):
        """ Cancels an item, item_id must be a value returned by
        coupon_add_item

        @param item_id:   the item id
        """

    def coupon_cancel():
        """ Can only be called when a coupon is opened. It needs to be
        possible to open new coupons after this is called.
        """

    def coupon_totalize(discount, charge, taxcode):
        """ Closes the coupon applies addition a discount or charge and tax.
        This can only be called when the coupon is open, has items added and
        payments added.

        @param discount:  discount in %
        @type discount:   Decimal between 0-100

        @param charge:    charge in %
        @type  charge     Decimal between 0-100

        @param tax_code:  currently unused

        @rtype:           Decimal
        @returns          the coupon total value
        """

    def coupon_add_payment(payment_method, value, description):
        """
        @param payment_method: The payment method.
        @type payment_method:  A constant (defined in the constants.py module)
                               representing the payment method.

        @param value:     The payment value
        @type value:      Decimal

        @param description: A simple description of the payment method to be
                            appended to the coupon.
        @type value:      str

        @rtype:           Decimal
        @returns          the total remaining amount
        """

    def coupon_close(message=''):
        """ It needs to be possible to open new coupons after this is called.
        You must call coupon_totalize before calling this method.

        @param message:   promotional message
        @type message:    str

        @rtype:           int
        @returns:         identifier of the coupon.
        """

    #
    # Base admin operations
    #

    def summarize():
        """ Prints a summary of all sales of the day. In Brazil this is
        'read X' operation.
        """

    def close_till():
        """ Close the till for the day, no other actions can be done after
        this is called. In Brazil this is 'reduce Z' operation
        """

    def till_add_cash(value):
        """ Add an till complement. This is called 'suprimento de caixa' on
        Brazil

        @param value:     The value added
        @type value:      Decimal
        """

    def till_remove_cash(value):
        """ Retire payments from the till. This is called 'sangria' on Brazil

        @param value:     The value to remove
        @type value:      Decimal
        """

    #
    # Getting printer status
    #

    def get_status():
        """ Returns a 3 sized tuple of boolean: Offline, OutOfPaper, Failure.
        """

    def get_capabilities():
        """ Returns a capabilities dictionary, where the keys are the strings
        below and its values are Capability instances

        * item_code           (str)
        * item_id             (int)
        * items_quantity      (float)
        * item_price          (float)
        * item_description    (str)
        * payment_value       (float)
        * payment_description (str)
        * promotional_message (str)
        * customer_name       (str)
        * customer_id         (str)
        * customer_address    (str)
        * add_cash_value      (float)
        * remove_cash_value   (float)
        """

class IChequePrinter(IPrinter):
    """ Interface specification for cheque printers. """

    cheque_printer_charset = Attribute("The charset name which the cheque "
                                       "printer uses.")

    def get_banks():
        """ Returns a dictionary of all banks supported by the printer. The
        dictionary's key is the bank name and its value are BankConfiguration
        instances (this classe [BankConfiguration] is used to store and manage
        the values of each section in the configuration file).
        """

    def print_cheque(bank, value, thirdparty, city, date=None):
        """ Prints a cheque

        @param bank:      the code of bank
        @type bank:       one of codes returned by get_banks method.

        @param value:     the value of the cheque
        @type value:      Decimal

        @param thirdparty: receiver of the cheque
        @type thirdparty: str

        @param city:
        @type city:       str

        @param date:      when the cheque was payed, optional
        @type date:       datetime
        """

    def get_capabilities():
        """ Returns a capabilities dictionary, where the keys are the strings
        below and its values are Capability instances

        * cheque_thirdparty   (str)
        * cheque_value        (Decimal)
        * cheque_city         (str)
        """
