
    # -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _
from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
import logging
_logger = logging.getLogger(__name__)
from datetime import date

class MxPromotionssale(models.Model):
    _inherit = 'sale.order'

    def _get_reward_values_free_shipping(self, program):
        delivery_line = self.order_line.filtered(lambda x: x.is_delivery)
        taxes = delivery_line.product_id.taxes_id
        
        if self.fiscal_position_id:
            taxes = self.fiscal_position_id.map_tax(taxes)
        return {
            'name': _("Discount: xDDDDDD ") + program.name,
            'product_id': program.discount_line_product_id.id,
            'price_unit': delivery_line and - delivery_line.price_unit or 0.0,
            'product_uom_qty': 1.0,
            'product_uom': program.discount_line_product_id.uom_id.id,
            'order_id': self.id,
            'is_reward_line': True,
            'tax_id': [(4, tax.id, False) for tax in taxes],
            'cupon_id':program.id,
            'promotions_applied_mx':[(0, 0,  { 'name':str(line.id) ,'ref_sol':line.id } ) for line in delivery_line   ]
        } 
    #REWARD MEX
    def _update_existing_reward_lines(self):
        '''Update values for already applied rewards'''
        def update_line(order, lines, values):
            '''Update the lines and return them if they should be deleted'''
            lines_to_remove = self.env['sale.order.line']
            # Check commit 6bb42904a03 for next if/else
            # Remove reward line if price or qty equal to 0
            
            if values['product_uom_qty'] and values['price_unit']:
                if lines.promotions_applied_mx:
                   lines.promotions_applied_mx = False
                lines.write(values)
            else:
                if program.reward_type != 'free_shipping':
                    # Can't remove the lines directly as we might be in a recordset loop
                    lines_to_remove += lines
                else:
                    if lines.promotions_applied_mx:
                        lines.promotions_applied_mx = False
                    values.update(price_unit=0.0)
                    lines.write(values)
            return lines_to_remove

        self.ensure_one()
        order = self
        applied_programs = order._get_applied_programs_with_rewards_on_current_order()
        for program in applied_programs:
            values = order._get_reward_line_values(program)
            lines = order.order_line.filtered(lambda line: line.product_id == program.discount_line_product_id)
            if program.reward_type == 'discount' and program.discount_type == 'percentage':
                lines_to_remove = lines
                # Values is what discount lines should really be, lines is what we got in the SO at the moment
                # 1. If values & lines match, we should update the line (or delete it if no qty or price?)
                # 2. If the value is not in the lines, we should add it
                # 3. if the lines contains a tax not in value, we should remove it
                for value in values:
                    value_found = False
                    for line in lines:
                        # Case 1.
                        if not len(set(line.tax_id.mapped('id')).symmetric_difference(set([v[1] for v in value['tax_id']]))):
                            value_found = True
                            # Working on Case 3.
                            lines_to_remove -= line
                            lines_to_remove += update_line(order, line, value)
                            continue
                    # Case 2.
                    if not value_found:
                        order.write({'order_line': [(0, False, value)]})
                # Case 3.
                lines_to_remove.unlink()
            else:
                update_line(order, lines, values[0]).unlink()
    #REWARD MEX
    def _get_reward_values_discount(self, program):
        if program.discount_type == 'fixed_amount':
            return [{
                'name': _("Discount: ") + program.name,
                'product_id': program.discount_line_product_id.id,
                'price_unit': - self._get_reward_values_discount_fixed_amount(program),
                'product_uom_qty': 1.0,
                'product_uom': program.discount_line_product_id.uom_id.id,
                'is_reward_line': True,
                'tax_id': [(4, tax.id, False) for tax in program.discount_line_product_id.taxes_id],
                'cupon_id':program.id
            }]
        reward_dict = {}
        lines = self._get_paid_order_lines()
        if program.discount_apply_on == 'cheapest_product':
            line = self._get_cheapest_line()
            if line:
                discount_line_amount = line.price_reduce * (program.discount_percentage / 100)
                if discount_line_amount:
                    taxes = line.tax_id
                    if self.fiscal_position_id:
                        taxes = self.fiscal_position_id.map_tax(taxes)

                    reward_dict[line.tax_id] = {
                        'name': _("Discount: ") + program.name,
                        'product_id': program.discount_line_product_id.id,
                        'price_unit': - discount_line_amount,
                        'product_uom_qty': 1.0,
                        'product_uom': program.discount_line_product_id.uom_id.id,
                        'is_reward_line': True,
                        'tax_id': [(4, tax.id, False) for tax in taxes],
                        'cupon_id':program.id,
                        'promotions_applied_mx':[(0, 0,  { 'name':str(line.id) ,'ref_sol':line.id } ) ] 
                        

                    }
        elif program.discount_apply_on in ['specific_products', 'on_order']:
            if program.discount_apply_on == 'specific_products':
                # We should not exclude reward line that offer this product since we need to offer only the discount on the real paid product (regular product - free product)
                free_product_lines = self.env['sale.coupon.program'].search([('reward_type', '=', 'product'), ('reward_product_id', 'in', program.discount_specific_product_ids.ids)]).mapped('discount_line_product_id')
                lines = lines.filtered(lambda x: x.product_id in (program.discount_specific_product_ids | free_product_lines))
               
            for line in lines:
                discount_line_amount = self._get_reward_values_discount_percentage_per_line(program, line)
                
                if discount_line_amount:

                    if line.tax_id in reward_dict:
                        reward_dict[line.tax_id]['price_unit'] -= discount_line_amount
                        if not  line.is_reward_line:
                            reward_dict[line.tax_id]['promotions_applied_mx'].append( (0, 0,  { 'name':str(line.id) ,'line_id':line.id } ) )
                    else:
                        taxes = line.tax_id
                        if self.fiscal_position_id:
                            taxes = self.fiscal_position_id.map_tax(taxes)

                        tax_name = ""
                        if len(taxes) == 1:
                            tax_name = " - " + _("On product with following tax: ") + ', '.join(taxes.mapped('name'))
                        elif len(taxes) > 1:
                            tax_name = " - " + _("On product with following taxes: ") + ', '.join(taxes.mapped('name'))

                        reward_dict[line.tax_id] = {
                            'name': _("Discount: ") + program.name + tax_name,
                            'product_id': program.discount_line_product_id.id,
                            'price_unit': - discount_line_amount,
                            'product_uom_qty': 1.0,
                            'product_uom': program.discount_line_product_id.uom_id.id,
                            'is_reward_line': True,
                            'tax_id': [(4, tax.id, False) for tax in taxes],
                            'cupon_id':program.id,
                            'promotions_applied_mx':[(0, 0,  { 'name':str(line.id) ,'ref_sol':line.id } )  ] if not  line.is_reward_line else []  
                        }

        # If there is a max amount for discount, we might have to limit some discount lines or completely remove some lines
        max_amount = program._compute_program_amount('discount_max_amount', self.currency_id)
        if max_amount > 0:
            amount_already_given = 0
            for val in list(reward_dict):
                amount_to_discount = amount_already_given + reward_dict[val]["price_unit"]
                if abs(amount_to_discount) > max_amount:
                    reward_dict[val]["price_unit"] = - (max_amount - abs(amount_already_given))
                    add_name = formatLang(self.env, max_amount, currency_obj=self.currency_id)
                    reward_dict[val]["name"] += "( " + _("limited to ") + add_name + ")"
                amount_already_given += reward_dict[val]["price_unit"]
                if reward_dict[val]["price_unit"] == 0:
                    del reward_dict[val]
        return reward_dict.values()
    #REWARD MEX
    def _get_reward_values_product(self, program):
        price_unit = self.order_line.filtered(lambda line: program.reward_product_id == line.product_id)[0].price_reduce

        order_lines = (self.order_line - self._get_reward_lines()).filtered(lambda x: program._is_valid_product(x.product_id))
        max_product_qty = sum(order_lines.mapped('product_uom_qty')) or 1
        # Remove needed quantity from reward quantity if same reward and rule product
        if program._is_valid_product(program.reward_product_id):
            # number of times the program should be applied
            program_in_order = max_product_qty // (program.rule_min_quantity + program.reward_product_quantity)
            # multipled by the reward qty
            reward_product_qty = program.reward_product_quantity * program_in_order
        else:
            reward_product_qty = min(max_product_qty, self.order_line.filtered(lambda x: x.product_id == program.reward_product_id).product_uom_qty)

        reward_qty = min(int(int(max_product_qty / program.rule_min_quantity) * program.reward_product_quantity), reward_product_qty)
        # Take the default taxes on the reward product, mapped with the fiscal position
        taxes = program.reward_product_id.taxes_id
        if self.fiscal_position_id:
            taxes = self.fiscal_position_id.map_tax(taxes)
        return {
             'cupon_id':program.id,
            'product_id': program.discount_line_product_id.id,
            'price_unit': - price_unit,
            'product_uom_qty': reward_qty,
            'is_reward_line': True,
            'name': _("Free Product") + " - " + program.reward_product_id.name,
            'product_uom': program.reward_product_id.uom_id.id,
            'tax_id': [(4, tax.id, False) for tax in taxes],
            'promotions_applied_mx':[(0, 0,  { 'name':str(line.id) ,'ref_sol':line.id } ) for line in order_lines if line.product_id == program.reward_product_id  ] 
        }
    def _check_updatable_reward(self,inv,changes_line):
         if changes_line:   
            inv.update( changes_line ) 
            inv._onchange_invoice_line_ids()
    #Reward MEX
    def _adjust_reward_invoice(self,inv,cup,changes_line,type_reward):
        changes_line={}
        changes_line['invoice_line_ids'] = []
        #Check applied prootions
        for lines_to_apply in cup.promotions_applied_mx:
            ref_id = lines_to_apply.ref_sol
            #Find sale line with related lines cupon
            real_line = inv.invoice_line_ids.filtered(lambda il: ref_id.id in  [ sl.id for sl in   il.sale_line_ids ] )
            remove_line_reward = inv.invoice_line_ids.filtered(lambda il: cup.id in  [ sl.id for sl in   il.sale_line_ids ] )
            changes_line['invoice_line_ids'].append( (2, remove_line_reward.id)   )
            if  cup.cupon_id.reward_product_quantity == real_line.quantity :
                if type_reward == 'free_reward':
                   changes_line['invoice_line_ids'].append( ( 1, real_line.id, { 'price_unit':0.1 } ) )
                else:
                    
                   changes_line['invoice_line_ids'].append( ( 1, real_line.id, { 'price_unit': ref_id.price_unit + cup.price_unit } ) )
            else:
                    #Dist all discount to specific line , being 2 x 1 , 3 x 1 , 2x3 ... 
                    real_amount = real_line.quantity * real_line.price_unit                  

                    res_amount =  remove_line_reward.quantity * remove_line_reward.price_unit
                                                                    
                    real_amount = real_amount +  res_amount
                
                    changes_line['invoice_line_ids'].append( ( 1, real_line.id, { 'price_unit':  (real_amount/real_line.quantity)  } ) )    
                    
        return changes_line
    def _create_invoices(self, grouped=False, final=False):
        res = super(MxPromotionssale, self)._create_invoices(grouped,final)
        for order in self:
            inv = res.filtered(lambda t: t.invoice_origin == order.name)
            if inv:
                #Coupon avaible
                have_coupouns = order.order_line.filtered(lambda ol: ol.is_reward_line and  ol.cupon_id)
                
                #CASE FREE PRODUCTS
                changes_line=False               
                for cup in have_coupouns.filtered(lambda ol: ol.cupon_id.reward_type == 'product'):   
                    #Get related lines to cupon
                    type_reward ="free_reward"
                    changes_line = self._adjust_reward_invoice(inv,cup,changes_line,type_reward)
                self._check_updatable_reward(inv,changes_line)
                #Free shipping
               
                #CASE FREE PRODUCTS SHIPPING
                changes_line=False 
                for cup in have_coupouns.filtered(lambda ol: ol.cupon_id.reward_type == 'free_shipping'):
                    type_reward ="free_reward"
                    changes_line = self._adjust_reward_invoice(inv,cup,changes_line,type_reward)
                self._check_updatable_reward(inv,changes_line)
                
                #CASE CHEPEASTE PRODUCT
                changes_line=False
                for cup in have_coupouns.filtered(lambda ol: ol.cupon_id.reward_type == 'discount' and  ol.cupon_id.discount_type == 'percentage' and ol.cupon_id.discount_apply_on == 'cheapest_product' ):
  
                    type_reward ="discount_porcent"
                    changes_line = self._adjust_reward_invoice(inv,cup,changes_line,type_reward)
                    self._check_updatable_reward(inv,changes_line)
                
                #CASE SPECIFIC PRODUCTS
                changes_line=False
                for cup in have_coupouns.filtered(lambda ol: ol.cupon_id.reward_type == 'discount' and  ol.cupon_id.discount_type == 'percentage' and ol.cupon_id.discount_apply_on == 'specific_products' ): 
                    type_reward ="discount_porcent"
                    changes_line = self._adjust_reward_invoice(inv,cup,changes_line,type_reward)
                    self._check_updatable_reward(inv,changes_line)
                                
                


 
    

  
    