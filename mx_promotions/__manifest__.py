# -*- coding: utf-8 -*-
{
    'name': "MX promotions ",

    'summary': """
        New features Odoo""",

    'description': """
        Inherit some views , new views , reports
    """,

    'author': "Estrasol -Kevin Daniel del Campo",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','product','sale','stock','sale_margin','sale_management','purchase'
    ,'stock_picking_batch','web','account','project','sale_coupon_delivery'],

    # always loaded
    'data': [
    #Views
      'security/ir.model.access.csv',
       


    ],  
     'qweb': [
        
         ]
        ,
    'demo': [
    ],
    'application': True,
}
