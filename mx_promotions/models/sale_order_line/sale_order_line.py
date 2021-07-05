# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _

from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
class fleximaticsaleorderlinelie(models.Model):
    _name = 'sale.order.line.reference'
    name = fields.Char('name')
    line_id =  fields.Many2one('sale.order.line', string="Lines aplied")
    ref_sol =  fields.Many2one('sale.order.line', string="Lines aplied")
    
class MxPromotionticsaleorderline(models.Model):
    _inherit = 'sale.order.line'
  
    cupon_id = fields.Many2one('sale.coupon.program', string="Applied promotion")
    promotions_applied_mx = fields.One2many('sale.order.line.reference', 'line_id', string='Refferences discunts')
    
    #REWARD MX REMOVE PROMOTIONS FROM INVOICE LINES
    #def _prepare_invoice_line(self):
    #  
    #    res = super(MxPromotionticsaleorderline, self)._prepare_invoice_line()
    #    
    #    return res
    
