"""
Script to insert high-quality demo data for the professional AutoDeal IA Hunter Dashboard
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_context
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission, ScrapingLog
from datetime import datetime, timezone, timedelta

def insert_demo_data():
    print("Initializing demo data insertion...")
    
    # 1. Clean existing demo data
    with get_db_context() as db:
        deleted = db.query(Vehicle).filter(Vehicle.source_id.like("demo_%")).delete(synchronize_session=False)
        db.query(ScrapingLog).delete() # Reset log counts to show fresh health
        db.commit()
        print(f"Cleaned {deleted} old demo listings.")

    # 2. Define premium demo vehicles
    demo_vehicles = [
        # --- MOTORCYCLES (KTM 125 / MT-07 / HORNET) ---
        {
            "source": Source.OLX,
            "source_id": "demo_moto1",
            "url": "https://www.olx.pt/d/anuncio/ktm-duke-125-como-nova-IDE456.html",
            "vehicle_type": VehicleType.motos,
            "brand": "KTM",
            "model": "Duke 125",
            "version": "ABS",
            "year": 2021,
            "km": 8500,
            "price": 3200.0,
            "estimated_value": 3950.0,
            "deal_score": 8.7,
            "profit_potential": 550.0,
            "profit_percentage": 17.2,
            "price_discount_percentage": 19.0,
            "buyer_profit": 550.0,
            "deal_grade": "excellent",
            "title": "KTM Duke 125 ABS 2021 - Único Dono",
            "description": "Vendo KTM Duke 125 de 2021 com apenas 8500km. Mota de garagem, sem acidentes nem quedas. Ideal para carta A1 (pode ser conduzida com carta de carro). Sistema de travagem ABS de dois canais, painel TFT com conectividade KTM MY RIDE, luzes Full LED. Toda original, revisões feitas sempre no concessionário oficial KTM (livro a comprovar).",
            "images": ["https://images.olx.pt/metadata/ktm_duke_125_1.jpg"],
            "image_count": 4,
            "location": "Lisboa",
            "district": "Lisboa",
            "fuel_type": FuelType.GASOLINE,
            "transmission": Transmission.MANUAL,
            "engine_size": 125,
            "horsepower": 15,
            # Motorcycle attributes
            "engine_type": "single",
            "riding_style": "naked",
            "has_abs": True,
            "has_traction_control": False,
            "license_category": "A1",
            "seat_height": 830,
            "wet_weight": 139,
            "condition_score": 9.2,
            "ai_approved": True,
            "ai_risk_score": 1.2,
            "ai_recommendation": "APPROVED",
            "lifecycle_status": "Descoberto",
            "first_seen": datetime.now(timezone.utc) - timedelta(hours=2)
        },
        # DUPLICATE of Duke 125 on Standvirtual
        {
            "source": Source.STANDVIRTUAL,
            "source_id": "demo_moto1_dup",
            "url": "https://www.standvirtual.com/motos/anuncio/ktm-125-duke-ID890.html",
            "vehicle_type": VehicleType.motos,
            "brand": "KTM",
            "model": "Duke 125",
            "version": "ABS TFT",
            "year": 2021,
            "km": 8500,
            "price": 3300.0,
            "estimated_value": 3950.0,
            "deal_score": 8.5,
            "profit_potential": 450.0,
            "profit_percentage": 13.6,
            "price_discount_percentage": 16.5,
            "buyer_profit": 450.0,
            "deal_grade": "excellent",
            "title": "KTM 125 Duke (2021) Excelente Estado",
            "description": "KTM 125 Duke nacional com 8.5k km. Assistida na marca, sem qualquer queda ou risco. Muito económica e ágil. Ecrã TFT, faróis em led, ABS. Excelente para iniciar no mundo das duas rodas.",
            "images": ["https://images.standvirtual.com/ktm_duke_125_dup.jpg"],
            "image_count": 5,
            "location": "Amadora",
            "district": "Lisboa",
            "fuel_type": FuelType.GASOLINE,
            "transmission": Transmission.MANUAL,
            "engine_size": 125,
            "horsepower": 15,
            # Motorcycle attributes
            "engine_type": "single",
            "riding_style": "naked",
            "has_abs": True,
            "has_traction_control": False,
            "license_category": "A1",
            "seat_height": 830,
            "wet_weight": 139,
            "condition_score": 9.2,
            "ai_approved": True,
            "ai_risk_score": 1.2,
            "ai_recommendation": "APPROVED",
            "lifecycle_status": "Descoberto",
            "first_seen": datetime.now(timezone.utc) - timedelta(hours=2)
        },
        {
            "source": Source.OLX,
            "source_id": "demo_moto2",
            "url": "https://www.olx.pt/d/anuncio/yamaha-mt-07-limitada-a2-IDE789.html",
            "vehicle_type": VehicleType.motos,
            "brand": "Yamaha",
            "model": "MT-07",
            "version": "A2 35kW",
            "year": 2020,
            "km": 15000,
            "price": 5400.0,
            "estimated_value": 6300.0,
            "deal_score": 9.1,
            "profit_potential": 700.0,
            "profit_percentage": 13.0,
            "price_discount_percentage": 14.3,
            "buyer_profit": 700.0,
            "deal_grade": "exceptional",
            "title": "Yamaha MT-07 Limitada A2 (2020)",
            "description": "Yamaha MT07 do ano 2020 limitada para carta A2 no documento (pode ser conduzida com 18 anos). 15.000 km reais. Extras: Escape completo SC Project (vai também o original), cogumelos de proteção de motor LSL, piscas LED, suporte de matrícula curto. Revisão efetuada recentemente com óleo Yamalube e filtro original. Pneus Bridgestone Battlax S22 a 80%. Mota imaculada sem qualquer queda ou risco.",
            "images": ["https://images.olx.pt/metadata/yamaha_mt07.jpg"],
            "image_count": 6,
            "location": "Porto",
            "district": "Porto",
            "fuel_type": FuelType.GASOLINE,
            "transmission": Transmission.MANUAL,
            "engine_size": 689,
            "horsepower": 48,  # A2 power limit
            # Motorcycle attributes
            "engine_type": "twin",
            "riding_style": "naked",
            "has_abs": True,
            "has_traction_control": False,
            "license_category": "A2",
            "seat_height": 805,
            "wet_weight": 184,
            "condition_score": 9.5,
            "ai_approved": True,
            "ai_risk_score": 0.8,
            "ai_recommendation": "APPROVED",
            "lifecycle_status": "Contactado",
            "first_seen": datetime.now(timezone.utc) - timedelta(days=1)
        },
        {
            "source": Source.OLX,
            "source_id": "demo_moto3",
            "url": "https://www.olx.pt/d/anuncio/honda-hornet-cb600f-imaculada-IDE999.html",
            "vehicle_type": VehicleType.motos,
            "brand": "Honda",
            "model": "CB 600F Hornet",
            "version": "CB600F",
            "year": 2008,
            "km": 32000,
            "price": 3800.0,
            "estimated_value": 4600.0,
            "deal_score": 8.4,
            "profit_potential": 600.0,
            "profit_percentage": 15.8,
            "price_discount_percentage": 17.4,
            "buyer_profit": 600.0,
            "deal_grade": "good",
            "title": "Honda Hornet CB600F 2008 Imaculada",
            "description": "Honda Hornet 600cc de 2008 (frente K7/K8 de injeção). Mota com 32.000 km reais. Sem acidentes. Sempre guardada em garagem coberta com capa. Extras: Cogumelos LSL, manetes curtas ajustáveis, espelhos desportivos. Pneu traseiro novo, revisão completa de fluidos e pastilhas há 500km. Som fantástico, comportamento irrepreensível.",
            "images": ["https://images.olx.pt/metadata/honda_hornet.jpg"],
            "image_count": 3,
            "location": "Braga",
            "district": "Braga",
            "fuel_type": FuelType.GASOLINE,
            "transmission": Transmission.MANUAL,
            "engine_size": 599,
            "horsepower": 102,
            # Motorcycle attributes
            "engine_type": "four-cylinder",
            "riding_style": "naked",
            "has_abs": False,
            "has_traction_control": False,
            "license_category": "A",
            "seat_height": 800,
            "wet_weight": 198,
            "condition_score": 8.6,
            "ai_approved": True,
            "ai_risk_score": 2.1,
            "ai_recommendation": "APPROVED",
            "lifecycle_status": "Negociado",
            "first_seen": datetime.now(timezone.utc) - timedelta(days=2)
        },
        # --- CARS (VOLKSWAGEN / BMW / MERCEDES) ---
        {
            "source": Source.OLX,
            "source_id": "demo_car1",
            "url": "https://www.olx.pt/d/anuncio/vw-golf-vii-1-6-tdi-confortline-IDE123.html",
            "vehicle_type": VehicleType.carros,
            "brand": "Volkswagen",
            "model": "Golf",
            "version": "1.6 TDI Confortline",
            "year": 2018,
            "km": 95000,
            "price": 13900.0,
            "estimated_value": 16500.0,
            "deal_score": 9.3,
            "profit_potential": 2100.0,
            "profit_percentage": 15.1,
            "price_discount_percentage": 15.8,
            "buyer_profit": 2100.0,
            "deal_grade": "exceptional",
            "title": "VW Golf VII 1.6 TDI BlueMotion Confortline (2018)",
            "description": "Excelente Volkswagen Golf VII nacional, motor 1.6 TDI de 115cv muito fiável e económico. 95k km certificados, histórico completo de revisões efetuadas em concessionário oficial VW. Versão Confortline com sensores de estacionamento frontais/traseiros, ecrã tátil multimédia com App Connect (Apple CarPlay & Android Auto), ar condicionado automático climatronic dual-zone, jantes de liga leve 16'', cruise control adaptativo, sensores de chuva e luz. Pneus Michelin novos. Vendedor particular, motivo de venda: carro de empresa.",
            "images": ["https://images.olx.pt/metadata/vw_golf_7.jpg"],
            "image_count": 8,
            "location": "Coimbra",
            "district": "Coimbra",
            "fuel_type": FuelType.DIESEL,
            "transmission": Transmission.MANUAL,
            "engine_size": 1598,
            "horsepower": 115,
            "condition_score": 9.4,
            "ai_approved": True,
            "ai_risk_score": 0.5,
            "ai_recommendation": "APPROVED",
            "lifecycle_status": "Proposta Feita",
            "first_seen": datetime.now(timezone.utc) - timedelta(hours=6)
        },
        {
            "source": Source.STANDVIRTUAL,
            "source_id": "demo_car2",
            "url": "https://www.standvirtual.com/carros/anuncio/bmw-320-d-pack-m-aut-ID321.html",
            "vehicle_type": VehicleType.carros,
            "brand": "BMW",
            "model": "Série 3",
            "version": "320d Pack M",
            "year": 2019,
            "km": 112000,
            "price": 27900.0,
            "estimated_value": 31500.0,
            "deal_score": 8.8,
            "profit_potential": 2600.0,
            "profit_percentage": 9.3,
            "price_discount_percentage": 11.4,
            "buyer_profit": 2600.0,
            "deal_grade": "excellent",
            "title": "BMW 320d Touring Pack M Auto (2019)",
            "description": "BMW 320d Touring de 190cv com caixa automática Steptronic de 8 velocidades e Pack M original interior e exterior. Faróis Full LED adaptativos, cockpit virtual profissional, teto de abrir panorâmico, bancos desportivos em alcantara com regulação elétrica, jantes M de 18 polegadas, suspensão M, mala elétrica. Viatura importada pelo próprio com livro de revisões digital BMW. 112.000km garantidos em contrato.",
            "images": ["https://images.standvirtual.com/bmw_320d.jpg"],
            "image_count": 12,
            "location": "Sintra",
            "district": "Lisboa",
            "fuel_type": FuelType.DIESEL,
            "transmission": Transmission.AUTOMATIC,
            "engine_size": 1995,
            "horsepower": 190,
            "condition_score": 8.9,
            "ai_approved": True,
            "ai_risk_score": 1.5,
            "ai_recommendation": "APPROVED",
            "lifecycle_status": "Negociado",
            "first_seen": datetime.now(timezone.utc) - timedelta(days=3)
        },
        {
            "source": Source.OLX,
            "source_id": "demo_car3",
            "url": "https://www.olx.pt/d/anuncio/peugeot-208-1-2-puretech-active-IDE111.html",
            "vehicle_type": VehicleType.carros,
            "brand": "Peugeot",
            "model": "208",
            "version": "1.2 PureTech Active",
            "year": 2017,
            "km": 88000,
            "price": 8200.0,
            "estimated_value": 9400.0,
            "deal_score": 8.6,
            "profit_potential": 900.0,
            "profit_percentage": 11.0,
            "price_discount_percentage": 12.8,
            "buyer_profit": 900.0,
            "deal_grade": "good",
            "title": "Peugeot 208 1.2 PureTech Active (2017)",
            "description": "Peugeot 208 em muito bom estado geral. Motor 1.2 PureTech a gasolina de 82cv, super económico e ágil para cidade. Equipado com ecrã multimédia central com bluetooth, ar condicionado, comandos no volante, retrovisores elétricos. Nacional, sem acidentes, de um só proprietário. IUC pago e inspeção feita sem anotações até 2027.",
            "images": ["https://images.olx.pt/peugeot_208.jpg"],
            "image_count": 5,
            "location": "Leiria",
            "district": "Leiria",
            "fuel_type": FuelType.GASOLINE,
            "transmission": Transmission.MANUAL,
            "engine_size": 1199,
            "horsepower": 82,
            "condition_score": 8.8,
            "ai_approved": True,
            "ai_risk_score": 1.0,
            "ai_recommendation": "APPROVED",
            "lifecycle_status": "Comprado",
            "first_seen": datetime.now(timezone.utc) - timedelta(days=4)
        },
        {
            "source": Source.AUTOSAPO,
            "source_id": "demo_car4",
            "url": "https://autos.sapo.pt/carros/anuncio/renault-clio-0-9-tce-zen-ID987.html",
            "vehicle_type": VehicleType.carros,
            "brand": "Renault",
            "model": "Clio",
            "version": "0.9 TCe Zen",
            "year": 2018,
            "km": 68000,
            "price": 9900.0,
            "estimated_value": 11200.0,
            "deal_score": 8.3,
            "profit_potential": 950.0,
            "profit_percentage": 9.6,
            "price_discount_percentage": 11.6,
            "buyer_profit": 950.0,
            "deal_grade": "good",
            "title": "Renault Clio 0.9 TCe Zen 90cv 2018",
            "description": "Renault Clio Zen com motor turbo 0.9 TCe a gasolina de 90cv. Apenas 68.000km de um só dono. Sistema de navegação GPS original Renault Media Nav, sensores de estacionamento traseiros, luzes diurnas LED, jantes de liga leve 16''. Revisão acabada de fazer e garantia de 18 meses incluída no preço.",
            "images": ["https://images.sapo.pt/renault_clio.jpg"],
            "image_count": 7,
            "location": "Viseu",
            "district": "Viseu",
            "fuel_type": FuelType.GASOLINE,
            "transmission": Transmission.MANUAL,
            "engine_size": 898,
            "horsepower": 90,
            "condition_score": 8.7,
            "ai_approved": True,
            "ai_risk_score": 1.1,
            "ai_recommendation": "APPROVED",
            "lifecycle_status": "Perdido",
            "first_seen": datetime.now(timezone.utc) - timedelta(days=5)
        }
    ]

    # 3. Insert demo vehicles
    with get_db_context() as db:
        for item in demo_vehicles:
            vehicle = Vehicle(**item)
            db.add(vehicle)
        db.commit()
    
    # 4. Insert mock scraping logs to show active system
    with get_db_context() as db:
        now = datetime.now(timezone.utc)
        logs = [
            ScrapingLog(
                source=Source.OLX,
                started_at=now - timedelta(minutes=45),
                finished_at=now - timedelta(minutes=42),
                status="completed",
                listings_found=48,
                listings_added=6,
                listings_updated=2
            ),
            ScrapingLog(
                source=Source.STANDVIRTUAL,
                started_at=now - timedelta(minutes=30),
                finished_at=now - timedelta(minutes=25),
                status="completed",
                listings_found=32,
                listings_added=4,
                listings_updated=5
            ),
            ScrapingLog(
                source=Source.AUTOSAPO,
                started_at=now - timedelta(minutes=15),
                finished_at=now - timedelta(minutes=12),
                status="completed",
                listings_found=24,
                listings_added=2,
                listings_updated=1
            )
        ]
        for l in logs:
            db.add(l)
        db.commit()

    print(f"Successfully inserted {len(demo_vehicles)} premium demo vehicles and status logs.")
    print("Demo setup complete! Ready to run the upgraded dashboard.")

if __name__ == "__main__":
    insert_demo_data()
