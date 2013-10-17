#!/usr/bin/python

from copy import copy

from ads_data import ads_data
from datetime import datetime
from ads_tools import convert_date

class ads_purchase_order(ads_data):

	data_type = 'FOUR'
	xml_root = 'COMMANDEFOURNISSEURS'

	def extract_picking_in(self, picking):
		"""
		Takes a stock.picking.in browse_record and extracts the
		appropriate data into self.data

		@param picking: browse_record(stock.picking.in)
		"""

		template = {
			'NUM_BL': picking.name,
			'DATE_PREVUE': convert_date(picking.date),
			'LIBELLE_FOURN': picking.partner_id.name,
		}

		for move in picking.move_lines:
			if picking.partner_id.id in [seller.name.id for seller in move.product_id.seller_ids]:
				code_art_fourn = [seller.product_code for seller in move.product_id.seller_ids if seller.name.id == picking.partner_id.id][0]
			else:
				code_art_fourn = None

			data = copy(template)
			data['CODE_ART'] = move.product_id.default_code or move.product_id.code or move.product_id.name
			data['CODE_ART_FOURN'] = code_art_fourn
			data['QTE_ATTENDUE'] = move.product_uos_qty
			self.insert_data('COMMANDEFOURNISSEUR', data)

	def process(self, pool, cr):
		"""
		Called when an XML file is downloaded from the ADS server. Override this method to
		do something with self.data in OpenERP.
		@param pool: OpenERP object pool
		@param cr: OpenERP database cursor
		@returns True if successful. If True, the xml file on the FTP server will be deleted.
		"""
		return False
