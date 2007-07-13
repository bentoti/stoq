import datetime

from stoqdrivers.enum import TaxType

from stoqlib.domain.test.domaintest import DomainTest
from stoqlib.domain.sellable import SellableTaxConstant
from stoqlib.lib.sintegragenerator import StoqlibSintegraGenerator
from stoqlib.lib.test.test_sintegra import compare_sintegra_file

class TestSintegraGenerator(DomainTest):

    def testRecevingOrder(self):
        sellable = self.create_sellable(id=9999)
        sellable.tax_constant = SellableTaxConstant(
            description="18",
            tax_type=int(TaxType.CUSTOM),
            tax_value=18,
            connection=self.trans)

        order = self.create_receiving_order()
        order.receival_date = datetime.date(2007, 6, 1)
        order_item = self.create_receiving_order_item(order, sellable=sellable)

        order.discount_value = 10
        #order.purchase.discount_value = 5
        #order.purchase.surcharge_value = 8
        #order.surcharge_value = 15
        #order.ipi_total = 10
        order.freight_total = 6
        order.secure_value = 6
        order.expense_value = 12

        order.purchase.status = order.purchase.ORDER_PENDING
        order.purchase.confirm()
        order.set_valid()
        order.confirm()

        sellable.id = 9999

        generator = StoqlibSintegraGenerator(self.trans,
                                             datetime.date(2007, 6, 1),
                                             datetime.date(2007, 6, 30))

        compare_sintegra_file(generator.sintegra, 'sintegra-receival')
