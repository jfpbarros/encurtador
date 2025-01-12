from ninja import Router
from .schemas import LinkSchema,UpdateLinkSchema
from .models import Links, Clicks
from django.shortcuts import get_object_or_404, redirect
import qrcode 
from io import BytesIO
import base64

shortener_router = Router()

@shortener_router.post('create/', response={200:LinkSchema, 409:dict})
def create(request, link_schema: LinkSchema):
    data = link_schema.to_model_data()
    token =  data['token']
    redirect_link = data['redirect_link']
    expiration_time = data['expiration_time']
    max_uniques_clicks = data['max_uniques_clicks']


    if token and Links.objects.filter(token=token).exists():
        return 409, {'error': 'Token já existe, use outro!'}

    link = Links (
        redirect_link = redirect_link,
        expiration_time = expiration_time,
        max_uniques_clicks = max_uniques_clicks,
        token = token 
    )

    #link = Links(**data) #transforma em Objeto

    link.save()

    return 200, LinkSchema.from_models(link)

@shortener_router.get('/{token}', response={200: None, 409:dict})
def redirect_link(request, token):
    link = get_object_or_404(Links, token=token, active=True)
    # Links.objects.filter(token=token).filter(active=True)
    if link.expired():
        return 409, {'error': 'Link expirado!'}
    
    uniques_clicks = Clicks.objects.filter(link=link).values('ip').distinct().count()

    if link.max_uniques_clicks and uniques_clicks >= link.max_uniques_clicks:
        return 404, {'error': 'Link Expirado!'}
    
    click = Clicks(
        link = link,
        ip = request.META['REMOTE_ADDR']
    )
    click.save()
    return redirect(link.redirect_link)

@shortener_router.put('/{link_id}/', response={200: UpdateLinkSchema, 409:dict})
def update_link(request, link_id: int, link_schema: UpdateLinkSchema):
    link = get_object_or_404(Links, id=link_id)

    data = link_schema.dict()

    token = data['token']
    
    if token and Links.objects.filter(token=token).exclude(id=link_id).exists():
        return 409, {'error': 'Token já existe, use outro!'}

    for field, value in data.items():
        if value:
            setattr(link, field, value)

    link.save()

    return 200, link

@shortener_router.get('statistics/{link_id}/', response={200: dict})
def statistics(request, link_id: int):
    link = get_object_or_404(Links, id=link_id)
    uniques_clicks = Clicks.objects.filter(link=link).values('ip').distinct().count()

    total_clicks = Clicks.objects.filter(link=link).values('ip').count()

    return 200, {'uniques_clicks': uniques_clicks, 'total_clicks': total_clicks}

def get_api_url(request, token):
    scheme = request.scheme
    host = request.get_host()
    
    return f"{scheme}://{host}/api/{token}"
    #return f"{host}/api/{token}"

@shortener_router.get('qrcode/{link_id}/', response={200: dict})
def get_qrcode(request, link_id:int):
    link = get_object_or_404(Links, id=link_id)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L, 
        box_size=10,
        border=4
    )
    try:
        api_url = get_api_url(request, link.token)
        #print(f"URL gerada: {get_api_url(request, link.token)}")
        qr.add_data(api_url)
        qr.make(fit=True)
    except Exception as e:
        print(f"Erro ao imprimir: {e}")

    content = BytesIO()
    img = qr.make_image(fill_color='black', back_color='white')
    img.save(content)

    data = base64.b64encode(content.getvalue()).decode('UTF-8')
    print(data)
    return 200, {'content_image': data}
