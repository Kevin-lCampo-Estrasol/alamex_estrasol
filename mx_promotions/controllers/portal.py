from odoo import fields, http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.payment.controllers.portal import PaymentProcessing
from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from odoo.osv import expression
import base64
import json
import pathlib
from datetime import datetime
from datetime import timedelta
from odoo.http import content_disposition, dispatch_rpc, request, \
    serialize_exception as _serialize_exception, Response
from odoo.tools.mimetypes import guess_mimetype
from xml.etree import ElementTree as ET
import struct
import sys
from pysimplesoap.client import SoapClient
import logging
import copy
_logger = logging.getLogger(__name__)
import pytz
class TransportistaPortal(CustomerPortal):

    def _prepare_portal_layout_values(self):
        values = super(TransportistaPortal, self)._prepare_portal_layout_values()
        usr = request.env['res.partner'].search([('user_ids.id' ,'=',request.env.user.id)])
        egresos = request.env['tms.egresos'].search_count([('nombre_proveedor.id','=',usr.parent_id.id)])
        egreso_count = egresos
        values.update({
            'egreso_count': egreso_count,
        })
        return values


    @http.route(['/my/egresos', '/my/egresos/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_quotes(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        egreso_count = request.env['tms.egresos']
        searchbar_sortings = {
                'fecha': {'label': _('Order Date'), 'order': 'date_order desc'},
        }
        domain=[]
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        if not sortby:
            sortby = 'fecha'

        order = searchbar_sortings[sortby]['order']
        egreso_count = request.env['tms.egresos'].search_count(domain)
        pager = portal_pager(
            url="/my/egresos",
            url_args={'date_begin': date_begin, 'date_end': date_end},
            total=egreso_count,
            page=page,
            step=self._items_per_page
        )
        #Buscar usuario
        #_logger.info('msgMMMMMMMM'+str(request.env.user.email) )
        usr = request.env['res.partner'].search([('user_ids.id' ,'=',request.env.user.id)])
        #_logger.info('msgMMMMMMMM'+str(usr.parent_id.id) )
        #for value in request.env['tms.egresos'].search([]):
        #     _logger.info('msgMMMMMMMM'+str(value.nombre_proveedor.id) )
        #_logger.info('id usuario'+str(usr.id) )
        #Buscar sus egresos
        egresos = request.env['tms.egresos'].search([('nombre_proveedor.id','=',usr.parent_id.id)], limit=self._items_per_page, offset=pager['offset'])
        #egresos = request.env['tms.egresos'].search([('nombre_proveedor.user_ids.id','=',request.env.user.id)], limit=self._items_per_page, offset=pager['offset'])
        #egresos = request.env['tms.egresos'].search([])
        #egresos = request.env['tms.egresos'].search(domain, limit=self._items_per_page, offset=pager['offset'])


        values.update({
            'quotations': egresos.sudo(),
            'page_name': 'egreso',
            'pager': pager,
            'default_url': '/my/egresos'


        })
        return request.render("tms.portal_my_transportista", values)


    @http.route(['/my/egresos/<int:id>'], type='http', auth="user", website=True)
    def portal_order_page(self, id, report_type=None, access_token=None, message=False, download=False, **kw):
        values = self._prepare_portal_layout_values()
        try:
            order_sudo = self._document_check_access('tms.egresos', id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        #if report_type in ('html', 'pdf', 'text'):
        #    return self._show_report(model=order_sudo, report_type=report_type, report_ref='school.action_report_saleorder', download=download)

        # use sudo to allow accessing/viewing orders for public user
        # only if he knows the private token
        now = fields.Date.today()

        # Log only once a day
        """
        if order_sudo and request.session.get('view_quote_%s' % order_sudo.id) != now and request.env.user.share and access_token:
            request.session['view_quote_%s' % order_sudo.id] = now
            body = _('Quotation viewed by customer')
            _message_post_helper(res_model='school.book', res_id=order_sudo.id, message=body, token=order_sudo.access_token, message_type='notification', subtype="mail.mt_note", partner_ids=order_sudo.user_id.sudo().partner_id.ids)
        """
        #Navegacion botenes entre valores
        usr = request.env['res.partner'].search([('user_ids.id' ,'=',request.env.user.id)])
        egresos = request.env['tms.egresos'].search([('nombre_proveedor.id','=',usr.parent_id.id)])
        filtro_egresos = [x.id for x in egresos]
        lim = len(filtro_egresos)
        actual = filtro_egresos.index(id)
        actual_right = actual+1
        actual_left = actual-1
        right = egresos[actual_right] if actual_right < lim else egresos[0]
        left = egresos[actual_left] if actual_left != -1 else egresos[0]



        #Left y Right  conserva el id de el sgte y anterior 
        values.update({
            'sale_order': order_sudo,
            'message': message,
            'token': access_token,
            'return_url': '/shop/payment/validate',
            'bootstrap_formatting': True,
            'left':left,
            'right':right,
            'report_type': 'html',
            }
            )
        """
        history = request.session.get('my_orders_history', [])
        values.update(get_records_pager(history, order_sudo))
        """
        return request.render('tms.sale_order_portal_template_ok', values)

    @http.route(['/asociar/factura'], type='http', methods=['POST'], auth="user", csrf=False)
    def test_path(self, **kw):
        
        data = json.loads(kw['json'])
        checkeds=[]
        for check in data:
            checkeds.append( check['id'] )
        egresos = request.env['tms.egresos'].browse( checkeds )

        for state in egresos:
            if state.nombre_proveedor.podo_obligatorio == True:
                if state.pod[-1].estatus != "aceptado":
                    return "El POD es obligatorio con estatus aceptado"
        name_file = kw['file'].filename
        if  not pathlib.Path(name_file).suffix in [".xml",".XML"]:
            return "Solo se permiten extenciones .xml "
        else:
            file_encodestr=base64.encodestring(kw['file'].read())
            file_encodestr2=base64.encodestring(kw['file'].read())
            file_decostr = base64.b64decode(file_encodestr)
            try:
               xml = ET.fromstring(str(file_decostr.decode()))
            except:
                return "XML con formato invalido"
            data = {
                   'rfc_emisor': xml[0].attrib['Rfc'],
                   'rfc_receptor': xml[1].attrib['Rfc'],
                   'total': xml.attrib['Total'],
                   'uuid': xml[4][0].attrib['UUID'],
            }
            service = 'https://consultaqr.facturaelectronica.sat.gob.mx/consultacfdiservice.svc?wsdl'
            client = SoapClient(wsdl = service)
            fac = '?re={rfc_emisor}&rr={rfc_receptor}&tt={total}&id={uuid}'.format(**data)
            res = client.Consulta(fac)
            if 'ConsultaResult' in res:
                   pass

            ids_orden=[]
            if res['ConsultaResult']['Estado'] in ['Vigente','Cancelado']:
                for value in egresos:
                    ids_orden.append((4,value.id))
                no_factura=kw['numero_factura']
                factura = request.env['tms.factura']

                factura = factura.create( {'factura_e':ids_orden,'tipo':'egresos','estatus':'recibida','numero_factura':xml[4][0].attrib['UUID'],'folio':xml.attrib['Folio'],'estatus_sat':"Exitoso SAT dice: " + res['ConsultaResult']['Estado'],'anexos':[(0,0,{'fecha':datetime.now(),'datas':file_encodestr,'datas_fname':name_file,'name':name_file})] } )

                return "Exitoso SAT dice: " + res['ConsultaResult']['Estado']
            else:
                return "No encontrado en SAT"


    @http.route(['/asociar/factura/addfile'], type='http', methods=['POST'], auth="user", csrf=False)
    def test_path_cuatro(self, **kw):
        data = json.loads(kw['json'])
        checkeds=[]
        for check in data:
            checkeds.append( check['id'] )
        egresos = request.env['tms.egresos'].browse( checkeds )
        factura = egresos[0].factura
        no_factura=kw['numero_factura']
        if str(factura.numero_factura) != str(no_factura):
            return "Factura no coincide"
        name_file = kw['file'].filename
        if  not pathlib.Path(name_file).suffix in [".pdf",".PDF"]:
            return "Solo se permiten extenciones .PDF"
        factura.write({'anexos':[(0,0,{'fecha':datetime.now(),'datas':base64.encodestring(kw['file'].read()),'datas_fname':name_file,'name':name_file})]})
        return "Exitoso"
        #return json.JSONEncoder().encode(kw)
    @http.route(['/asociar/complemento'], type='http', methods=['POST'], auth="user", csrf=False)
    def test_path_cinco(self, **kw):
        data = json.loads(kw['json'])
        checkeds=[]
        for check in data:
            checkeds.append( check['id'] )
        egresos = request.env['tms.egresos'].browse( checkeds )
        factura = egresos[0].factura
        complemento_disp = egresos[0].ctnclt_egr.complemento_pago
        if not complemento_disp:
            return "No puedes subir complementos"
        no_factura=kw['numero_factura']
        if str(factura.numero_factura) != str(no_factura):
            return "Factura no coincide"
        name_file = kw['file'].filename

        factura.write({'anexos_factura':[(0,0,{'estatus_c':'recibidoc','fecha':datetime.now(),'datas':base64.encodestring(kw['file'].read()),'datas_fname':name_file,'name':kw['nombre_complemento'] if kw['nombre_complemento'] else "sin nombre"})]})
        return "Exitoso"

    @http.route(['/todo'], type='http', methods=['GET'], auth="user", csrf=False)
    def todo(self, **kw):
        return "Exitoso"
        #return json.JSONEncoder().encode(kw)
    @http.route(['/asociar/pod'], type='http', methods=['POST'], auth="user", csrf=False)
    def asoc_pod(self, **kw):
        data = json.loads(kw['json'])
        name_file = kw['file'].filename
        checkeds=[]
        for check in data:
            checkeds.append( check['id'] )
        egresos = request.env['tms.egresos'].browse( checkeds )
        if egresos[0].estatus_egr:
            if egresos[0].estatus_egr == "aceptado":
                return "Se encuentra POD aceptado"

        for egreso in egresos:
            egreso.write({'estatus_egr':'recibido','estatus_egrDos':'recibido','pod':[(0,0,
                                {'estatus':'recibido','fecha':datetime.now(),'datas':base64.encodestring(kw['file'].read()),
                                'datas_fname':name_file,'name':kw['nombre_pod'] if kw['nombre_pod'] else "sin nombre",'res_model':"tms.egresos",'res_id':egreso.id})]
                                }
                        )

        return str("Exitoso")

    @http.route(['/web/binary/download_document/<int:id>'], type='http', auth="user",csrf=False)
    def test_path_tres(self,id,**kw):
         egresos = request.env['tms.pod'].search([('id','=',id)])
         filecontent = base64.b64decode(egresos.archivo)
         return request.make_response(filecontent,
                            [('Content-Type', 'application/octet-stream'),
                             ('Content-Disposition', content_disposition(egresos.file_name))])
    @http.route(['/web/binary/download_document/factura/<int:id>'], type='http', auth="user",csrf=False)
    def test_path_factura_anexo(self,id,**kw):
         anexos = request.env['ir.attachment'].search([('id','=',id)])
         filecontent = base64.b64decode(anexos.datas)
         return request.make_response(filecontent,
                            [('Content-Type', 'application/octet-stream'),
                             ('Content-Disposition', content_disposition(anexos.datas_fname))])
    @http.route(['/web/binary/download_document/pod/<int:id>'], type='http', auth="public",csrf=False)
    def test_path_factura(self,id,**kw):
         anexos = request.env['tms.pod'].search([('id','=',id)])
         filecontent = base64.b64decode(anexos.archivo)
         return request.make_response(filecontent,
                            [('Content-Type', 'application/octet-stream'),
                             ('Content-Disposition', content_disposition(anexos.file_name))])
    @http.route(['/web/binary/download_document/factura_anexos/<int:id>'], type='http', auth="public",csrf=False)
    def test_path_tres_factura_complemento(self,id,**kw):
         anexos = request.env['tms.anexos_factura'].search([('id','=',id)])
         filecontent = base64.b64decode(anexos.anexos)
         return request.make_response(filecontent,
                            [('Content-Type', 'application/octet-stream'),
                             ('Content-Disposition', content_disposition(anexos.datas_fname))])
    @http.route(['/web/binary/download_document/factura_anexos_test/<int:id>'], type='http', auth="public",csrf=False)
    def test_path_tres_factura_complemento_test(self,id,**kw):
         anexos = request.env['tms.anexos'].search([('id','=',id)])
         filecontent = base64.b64decode(anexos.anexos)
         try:
            #with open("imageToSave444.xml", "wb") as imgFile:
            #    imgFile.write(base64.b64decode(anexos.anexos))
            xml = ET.fromstring(str(filecontent.decode()))

            data = {
                'rfc_emisor': xml[0].attrib['Rfc'],
                'rfc_receptor': xml[1].attrib['Rfc'],
                'total': xml.attrib['Total'],
                'uuid': xml[4][0].attrib['UUID'],
            }
            service = 'https://consultaqr.facturaelectronica.sat.gob.mx/consultacfdiservice.svc?wsdl'
            client = SoapClient(wsdl = service)
            fac = '?re={rfc_emisor}&rr={rfc_receptor}&tt={total}&id={uuid}'.format(**data)
            res = client.Consulta(fac)
            if 'ConsultaResult' in res:
                pass
                #print ('Estatus: %s' % res['ConsultaResult']['Estado'])
                #print ('Código de Estatus: %s' % res['ConsultaResult']['CodigoEstatus'])
                #print ('Código de Estatus: %s' % res['ConsultaResult'])
            return res['ConsultaResult']['Estado']

         except:
                return  "fallo"
         return "str(root)"
