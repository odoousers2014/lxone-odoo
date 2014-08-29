from openerp.osv import osv, fields
from openerp.tools.translate import _

import json

from auto_vivification import AutoVivification
from manager import get_lx_data_subclass

class lx_update(osv.osv):
    """
    These records represent data coming from LX1. Each one should be able to be executed
    independently from the rest, i.e. the reception of a picking order or a physical inventory.

    They are designed to be generated by the parsed xml in an lx.file.incoming, that is downloaded from 
    LX1's FTP server, and executed in the same order that they were created.
    """

    _name = 'lx.update'
    
    def _get_name(self, cr, uid, ids, field_name, arg, context):
        res = dict.fromkeys(ids)
        for update in self.browse(cr, uid, ids, context=context):
            res[update.id] = '%s, Node %s' % (update.file_incoming_id.xml_file_name, update.node_number)
        return res

    _columns = {
        'name': fields.function(_get_name, type='char', method=True, string="Name", help="The name of the file and the number of the XML node that contained this data"),
        'create_date' : fields.datetime('Create Date', readonly=True),
        'file_incoming_id': fields.many2one('lx.file.incoming', 'File', help="The file that is responsible for this update"),
        'sequence': fields.char('Execution Sequence', required=True, readonly=True, help="This field determines the order that updates will be processed"),
        'state': fields.selection( (
                ('to_execute', 'To Execute'), 
                ('executed', 'Executed'), 
                ('failed', 'Failed')
            ), 'State', help="The state field indicates the progression along the process workflow of the update"),
        'object_type': fields.char('Object Type', size=128, required=True, readonly=True, help="The type of data contained in this update"),
        'data': fields.text('Data', required=True, help="The data in JSON format that was downloaded from LX1"),
        'result': fields.text('Execution Result', readonly=True, help="Any errors during the update execution process will be saved here"),
        'node_number': fields.integer('XML Node Number', required=True, readonly=True, help="The XML node number in the file that created this update"),
    }

    _defaults = { 
        'state': 'to_execute',
        'sequence': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'lx.update')
    }
    
    def _sanitize_values(self, vals):
        """ Pretty print data field contents """
        if vals.get('data'):
            if isinstance(vals['data'], (dict, list, tuple, AutoVivification)):
                vals['data'] = json.dumps(vals['data'], indent=4, ensure_ascii=False)
            
        if 'state' in vals and 'result' not in vals:
            vals['result'] = ''
            
        return vals
    
    def create(self, cr, uid, vals, context=None):
        """ Sanitize values """
        vals = self._sanitize_values(vals)
        return super(lx_update, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        """ sanitize values """
        vals = self._sanitize_values(vals)
        return super(lx_update, self).write(cr, uid, ids, vals, context=context)

    def execute(self, cr, uid, ids, context=None):
        """
        Sorts IDs by their sequence, then find an appropriate lx_data child class based on 
        the update.object_type, instantiate it and call process.
        Then set state to executed, or catch errors and set as failed.
        """
        updates = self.read(cr, uid, ids, ['sequence'], context=context)
        updates.sort(key=lambda update: int(update['sequence']))
        for update in updates:
            update = self.browse(cr, uid, update['id'], context=context)
            
            if update.state == 'executed':
                continue
            
            # do execution
            try:
                # find appropriate lx_data class, instantiate it, and trigger process
                data = json.loads(update.data)
                lx_cls = get_lx_data_subclass(update.object_type)
                cls = lx_cls(data)
                cls.process(self.pool, cr, data)
            
                # change state
                update.write({'state': 'executed'})
                
                # trigger update.file state check
                update.file_incoming_id.check_still_waiting()
                
            except Exception, e:
                result = 'Error while executing: %s' % unicode(e)
                update.write({'state': 'failed', 'result': result})

    def execute_all(self, cr, uid, ids=[], context=None):
        """ Gets ids for all updates whose state is not executed and calls execute on them """
        all_ids = self.search(cr, uid, [('state', '!=', 'executed')], context=context)
        self.execute(cr, uid, all_ids)

    def unlink(self, cr, uid, ids, context=None):
        raise osv.except_osv(_('Cannot Delete'), _('Deletion has been disabled for update records because it is important to maintain a complete audit trail'))
