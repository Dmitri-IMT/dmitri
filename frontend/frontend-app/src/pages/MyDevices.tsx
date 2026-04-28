import { useState, useEffect } from 'react';
import { Card, Btn } from '../components/ui';
import { Icon } from '../components/icons/Icon';

interface ScannerDevice {
  id: string;
  name: string;
  serial: string;
  status: 'online' | 'offline';
  last_seen: string;
}

export default function MyDevices() {
  const [scanners, setScanners] = useState<ScannerDevice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchScanners = async () => {
      setLoading(true);
      
      // TODO: Integração com o Backend FastAPI
      /*
      try {
        const response = await fetch('http://localhost:8000/api/v1/my-scanners');
        const data = await response.json();
        setScanners(data);
      } catch (error) {
        console.error("Erro ao buscar scanners:", error);
      } finally {
        setLoading(false);
      }
      */

      // Simulando falha/atraso da requisição enquanto não há backend
      setTimeout(() => {
        setLoading(false);
        // setScanners([]); // Mantendo vazio conforme solicitado
      }, 800);
    };

    fetchScanners();
  }, []);

  const handleDisconnect = (id: string) => {
    if (window.confirm("Tem certeza que deseja desconectar este scanner?")) {
      console.log(`Desconectando scanner: ${id}`);
      // TODO: Chamada para deletar/desconectar no back
      setScanners(prev => prev.filter(s => s.id !== id));
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '100px' }}>
        <div style={{ animation: 'pulse 1.5s infinite', color: 'var(--accent)' }}>
          <Icon n="scan" s={40} />
        </div>
      </div>
    );
  }

  function addNewDevice() {
    alert('Function not implemented.');
    throw new Error('Function not implemented.');
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, animation: 'fadeIn 0.3s ease' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>Meus Dispositivos</h2>
          <p style={{ color: 'var(--text3)', fontSize: 14, marginTop: 4 }}>Gerencie seus agentes de hardware Dmitri</p>
        </div>
        <Btn icon="plus" onClick={ addNewDevice }>
          Adicionar Novo
        </Btn>
      </div>

      {scanners.length === 0 ? (
        <Card style={{ padding: '60px 20px', textAlign: 'center', borderStyle: 'dashed' }}>
          <div style={{ marginBottom: 16, opacity: 0.5 }}>
            <Icon n="network" s={48} c="var(--text3)" />
          </div>
          <h3 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text2)' }}>Nenhum dispositivo conectado</h3>
          <p style={{ color: 'var(--text3)', fontSize: 14, marginTop: 8, maxWidth: 400, marginInline: 'auto' }}>
            Você ainda não possui scanners Dmitri vinculados à sua conta. Conecte o hardware à energia e clique no botão abaixo.
          </p>
          <Btn 
            variant="secondary" 
            style={{ marginTop: 24 }} 
            icon="plus"
            onClick={ addNewDevice }
          >
            Configurar meu primeiro scanner
          </Btn>
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {scanners.map(scanner => (
            <Card key={scanner.id} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <div style={{ width: 40, height: 40, borderRadius: 8, background: 'var(--surface2)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border)' }}>
                    <Icon n="terminal" s={20} c={scanner.status === 'online' ? 'var(--ok)' : 'var(--text3)'} />
                  </div>
                  <div>
                    <h4 style={{ fontSize: 15, fontWeight: 600 }}>{scanner.name}</h4>
                    <span style={{ fontSize: 11, color: 'var(--text3)', fontFamily: 'var(--mono)' }}>SN: {scanner.serial}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: scanner.status === 'online' ? 'var(--ok)' : 'var(--urgente)' }} />
                  <span style={{ fontSize: 12, color: scanner.status === 'online' ? 'var(--ok)' : 'var(--urgente)', fontWeight: 600 }}>
                    {scanner.status.toUpperCase()}
                  </span>
                </div>
              </div>

              <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: 'var(--text3)' }}>Visto pela última vez: {scanner.last_seen}</span>
                <Btn 
                  variant="ghost" 
                  size="sm" 
                  style={{ color: 'var(--urgente)' }} 
                  onClick={() => handleDisconnect(scanner.id)}
                >
                  Desconectar
                </Btn>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}