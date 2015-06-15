"""libanac - SINTAC (Sistema Integrado de Informacao da Aviacao Civil) access
and session management"""

import datetime
import os
import re
from requests import Session
from threading import Thread
from time import sleep
from bs4 import BeautifulSoup


class LogBookValidationError(Exception):
    """Log book fields validation error"""
    pass


class SINTACError(Exception):
    """Authentication error"""
    pass


class SINTACSession(Session):
    """SINTAC session management

    :param str username: user name
    :param str password: user password
    """
    __base_url__ = 'https://sistemas.anac.gov.br/'
    __expired__ = False
    __keep_alive__ = None
    __password__ = None
    __username__ = None

    def __init__(self, username, password):
        super(SINTACSession, self).__init__()

        self.headers['Referer'] = self.__base_url__

        self.__username__ = username
        self.__password__ = password

        try:
            self.login()

        except SINTACError:
            self.__expired__ = True
            raise

    def __repr__(self):
        return '<{0}.{1}: "{2}">'.format(self.__class__.__module__,
                                         self.__class__.__name__,
                                         self.__username__.upper())

    def close(self):
        """Closes all adapters and as such the session"""
        if not self.__expired__:
            self.logout()

        super(SINTACSession, self).close()

    def request(self, method, url, params=None, data=None, headers=None,
                cookies=None, files=None, auth=None, timeout=None,
                allow_redirects=True, proxies=None, hooks=None, stream=None,
                verify=None, cert=None, json=None):
        """Constructs a :class:`Request <Request>`, prepares it and sends it.
        Returns :class:`Response <Response>` object.

        :param method: method for the new :class:`Request` object.
        :param url: URL for the new :class:`Request` object.
        :param params: (optional) Dictionary or bytes to be sent in the query
            string for the :class:`Request`.
        :param data: (optional) Dictionary or bytes to send in the body of the
            :class:`Request`.
        :param json: (optional) json to send in the body of the
            :class:`Request`.
        :param headers: (optional) Dictionary of HTTP Headers to send with the
            :class:`Request`.
        :param cookies: (optional) Dict or CookieJar object to send with the
            :class:`Request`.
        :param files: (optional) Dictionary of ``'filename': file-like-objects``
            for multipart encoding upload.
        :param auth: (optional) Auth tuple or callable to enable
            Basic/Digest/Custom HTTP Auth.
        :param timeout: (optional) How long to wait for the server to send
            data before giving up, as a float, or a (`connect timeout, read
            timeout <user/advanced.html#timeouts>`_) tuple.
        :type timeout: float or tuple
        :param allow_redirects: (optional) Set to True by default.
        :type allow_redirects: bool
        :param proxies: (optional) Dictionary mapping protocol to the URL of
            the proxy.
        :param stream: (optional) whether to immediately download the response
            content. Defaults to ``False``.
        :param verify: (optional) if ``True``, the SSL cert will be verified.
            A CA_BUNDLE path can also be provided.
        :param cert: (optional) if String, path to ssl client cert file (.pem).
            If Tuple, ('cert', 'key') pair.
        """

        if self.__expired__:
            self.login()

        if url.startswith('/'):
            url = self.__base_url__ + url[1:]

        if verify is None:
            verify = os.path.join(os.path.dirname(__file__),
                                  'ICP_Brasilv2.crt')

        response = super(SINTACSession, self).request(
            method=method, url=url, params=params, data=data, headers=headers,
            cookies=cookies, files=files, auth=auth, timeout=timeout,
            allow_redirects=allow_redirects, proxies=proxies, hooks=hooks,
            stream=stream, verify=verify, cert=cert, json=json
        )

        alert = re.search(r'''<script language=['"]javaScript['"]>\s*(/\*)?\s*alert\(['"](?P<message>.*?)['"]\)''',
                          response.text, re.IGNORECASE)

        if alert is not None:
            raise SINTACError(alert.group('message').encode('utf8'))

        return response

    def change_password(self, password):
        """Change user password

        :param str password: new password
        """
        self.post('/SACI/Login.asp', data={
            'acao': 'SNS',
            'txtLogin': self.__username__,
            'txtSenha': password,
            'txtSenhaAtual': self.__password__,
            'txtSenhaNova': password,
            'txtSenhaNova2': password,
        })

        self.__password__ = password

    def get_login(self):
        """Return session username

        :return: the session username
        :rtype: str
        """
        return self.get('/SACI/SCA/ACESSO/getSessaoLogin.asp').text

    # noinspection PyBroadException
    def keep_alive(self):
        """Test credentials every 5 seconds and close session if expired"""

        try:
            while self.get_login().upper() == self.__username__.upper():
                sleep(5)

        except:
            pass

        finally:
            self.close()

    def login(self):
        """Authenticate using the provided credentials

        :raises SINTACError: if provided credentials are invalid
        """
        self.__expired__ = False

        if self.__keep_alive__ is not None:
            while self.__keep_alive__.is_alive():
                self.__keep_alive__.join(60)

        self.post('/SACI/', data={
            'acao': 'VL',
            'txtLogin': self.__username__,
            'txtSenha': self.__password__,
            })

        self.__keep_alive__ = Thread(target=self.keep_alive,
                                     name='KeepAliveThread')
        self.__keep_alive__.daemon = True
        self.__keep_alive__.start()

    def logout(self):
        """Logout"""
        self.get('/sintac/ResultadoExecutarLogout.do')
        self.__expired__ = True


class LogBook(SINTACSession):
    """LogBook session management

    :param str username: user name
    :param str password: user password
    """

    __logbook_id__ = None
    __roles__ = {
        '02': 'Second-in-command',
        '03': 'Flight instructor',
        '06': 'Pilot-in-command',
        '07': 'Student pilot'
    }

    def __init__(self, username, password):
        super(LogBook, self).__init__(username=username, password=password)

        self.__logbook_id__ = self.get_logbook_id()

    def add_draft(self, date, ldg, role, reg, dep, dst, rmk=None, day_t=None,
                  ngt_t=None, xc_t=None, instr_t=None, hood_t=None):
        """Insert a log book draft entry

        :param str date: flight date (dd/mm/yyyy)
        :param str ldg: number of landings
        :param str role: pilot role:
         02: SIC, 03: CFI, 06: PIC, 07: student pilot
        :param str reg: aircraft registration number
        :param str dep: departure airport (ICAO)
        :param str dst: destination airport (ICAO)
        :param str rmk: remarks and endorsements
        :param str day_t: day flight time (hh:mm or h.d)
        :param str ngt_t: night flight time (hh:mm or h.d)
        :param str xc_t: cross-country flight time (hh:mm or h.d)
        :param str instr_t: actual instrument flight time (hh:mm or h.d)
        :param str hood_t: under the hood instrument time (hh:mm or h.d)
        """
        #TODO: support python objects as parameters

        # Flight date validation
        try:
            date = datetime.datetime(
                *(int(x) for x in reversed(date.split('/', 3)))
            ).strftime('%d/%m/%Y')

        except:
            raise LogBookValidationError('Formato de data invalido: {0!r}'
                                         .format(date))

        # Number of landings validation
        try:
            ldg = '{0:02d}'.format(int(ldg))

        except:
            raise LogBookValidationError('Numero de pousos deve ser um '
                                         'numeral')

        # Pilot role validation
        try:
            if role not in self.__roles__.keys():
                raise ValueError

        except:
            raise LogBookValidationError('Valor invalido para funcao a bordo: '
                                         '{0!r}'.format(role))

        # Aircraft registration number validation
        try:
            reg = reg.replace('-', '')
            if len(reg) != 5:
                raise ValueError

        except:
            raise LogBookValidationError('Matricula invalida: {0!r}'
                                         .format(reg))

        # Departure airport validation
        try:
            dep = dep.upper()
            if len(dep) != 4:
                raise ValueError

        except:
            raise LogBookValidationError('Aerodromo de origem invalido: {0!r}'
                                         .format(dep))

        # Destination airport validation
        try:
            dst = dst.upper()
            if len(dst) != 4:
                raise ValueError

        except:
            raise LogBookValidationError('Aerodromo de destino invalido: {0!r}'
                                         .format(dst))

        # Remarks and endorsements validation
        try:
            if rmk is not None and len(rmk) > 4000:
                raise ValueError

        except:
            raise LogBookValidationError('Observacao invalida: {0!r}'
                                         .format(rmk))

        # Flight time validation
        if day_t is None and ngt_t is None:
            raise LogBookValidationError('Preencha as horas em voo')

        if instr_t is not None and hood_t is not None:
            raise LogBookValidationError('Nao e permitida fazer esta '
                                         'combinacao de horas')

        def fmt_t(t):
            try:
                if t is None:
                    return

                if ',' in t:
                    t.replace(',', '.')

                if '.' in t:
                    t_int, t_dec = t.split('.', 1)
                    t_dec = int(t_dec) * 6
                    t = '{0}:{1}'.format(t_int, t_dec)

                return datetime.time(
                    *(int(x) for x in t.split(':', 2))
                ).strftime('%H:%M')

            except:
                raise LogBookValidationError('Formato de hora invalido: {0!r}'
                                             .format(t))

        day_t = fmt_t(day_t)
        ngt_t = fmt_t(ngt_t)
        xc_t = fmt_t(xc_t)
        instr_t = fmt_t(instr_t)
        hood_t = fmt_t(hood_t)

        # Aircraft class and airworthiness category validation
        acft = self.get_acft(reg)
        if acft['cd_categoria'] in ['TPN', 'TPX', 'TPR']:
            raise LogBookValidationError('O registro de horas de empresas '
                                         'aereas deve ser feito pela propria '
                                         'empresa.')

        data = {
            'acao': 'I',
            'ID_AERONAUTA': self.__logbook_id__,
            'ID_HABILITACAO': acft['id_dominio_habilitacao'],
            'CD_HABILITACAO': acft['cd_tipo'],
            'txtDataVoo': date,
            'txtPousos': ldg,
            'cmbFuncao': role,
            'txtObservacao': rmk,
            'cmbSimulador': 'N',
            'txtMatricula': reg,
            'hdhabilitacao': acft['cd_categoria'],
            'txtOrigem': dep,
            'txtDestino': dst,
            'txtDiurno': day_t,
            'txtNoturno': ngt_t,
            'txtNavegacao': xc_t,
            'txtInstrumento': instr_t,
            'txtCapota': hood_t,
            'salvar': 'Salvar+rascunho',
        }

        try:
            self.post('/SACI/CIV/Digital/manter.asp', data=data)

        except SINTACError as e:
            if not e.message.endswith('sucesso!'):
                raise

    def get_acft(self, registration):
        """Get aircraft class and airworthiness category

        :param str registration: aircraft registration
        :return: a dictionary containing the aircraft class and airworthiness
        category
        :rtype: dict
        :raises SINTACError: if the aircraft registration is not found
        """
        registration = registration.replace('-', '')

        response = BeautifulSoup(
            self.get('/SACI/CIV/Digital/buscaHabilitacaoXML.asp',
                     params={'CD_MARCA': registration}).text)

        if not response.elementos.elemento:
            raise SINTACError('Aircraft registration not found')

        return dict((t.name, t.text) for t in
                    response.elementos.elemento.children)

    def get_logbook_id(self):
        """Get user log book id"""

        response = self.get('/SACI/CIV/Digital/incluir.asp')
        logbook_id = re.search(r'''\s*name=['"]ID_AERONAUTA['"]\s*value=['"](?P<id>[0-9]+)['"]\s*''',
                               response.text, re.IGNORECASE)

        if logbook_id:
            return logbook_id.group('id')

        raise SINTACError('Could not get pilot logbook id')